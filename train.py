import datetime
import json
import numpy as np
import os
import pathlib
import time

from matplotlib import pyplot as plt
from sklearn.utils import class_weight
from sklearn.metrics import classification_report

import torch
import torch.utils.data
from torch import nn
import torchvision

import presets
import utils
import dataloader
from loss import DiceLoss


plt.rcParams["figure.figsize"] = (12, 5)

DEBUG = False

# target names for classification report
target_names = ['background', 'edema', 'non-enhancing tumor', 'enhancing tumour']


def get_transform(train):
    base_size = 256
    crop_size = 256
    return presets.SegmentationPresetTrain(base_size, crop_size) if train else presets.SegmentationPresetEval(base_size)


# loss function used for previous work
def criterion(inputs, target):

    loss = nn.functional.cross_entropy(inputs, target, ignore_index=128)

    return loss


def evaluate(model, data_loader, device, num_classes, visualize, epoch, num_epochs):
    ##### variables for evaluation criteria ######
    i = 1
    isdefect_output = 0
    isdefectfree_output = 0
    pred_defper = []
    actual_defper = []
    target_class = torch.Tensor([])
    pred_class = torch.Tensor([])
    #############################################
    model.eval()
    confmat = utils.ConfusionMatrix(num_classes)
    metric_logger = utils.MetricLogger(delimiter="  ")
    header = 'Val:'
    with torch.no_grad():
        for image, target in metric_logger.log_every(data_loader, 100, header):
            prev_time = time.time()
            target_class = torch.cat((target_class, target.flatten()), dim=0)
            image, target = image.to(device), target.to(device)
            output = model(image)
            output = output.argmax(1)

            # on last epoch, will create visuals if visualize flag is True
            if visualize:
                output_cpu = output.cpu()
                pred_class = torch.cat((pred_class, output_cpu.flatten()), dim=0)
                save_path = './visualize/epoch' + str(epoch) + '/'
                pathlib.Path(save_path).mkdir(parents=True, exist_ok=True)

                target_zero = target[0].cpu()
                target_zero[target_zero == 128] = 0
                tar_count = np.count_nonzero(target_zero)
                output_pix = np.count_nonzero(output_cpu)

                if tar_count == 0:
                    if output_pix <= 1:
                        isdefectfree_output += 1
                else:
                    if output_pix > 1:
                        isdefect_output += 1

                output_defect_percent = float(output_pix) / np.size(output_cpu.numpy())
                target_defect_percent = float(tar_count) / np.size(target_zero.numpy())

                output_defect_percent = output_defect_percent * 100
                target_defect_percent = target_defect_percent * 100

                pred_defper.append(output_defect_percent)
                actual_defper.append(target_defect_percent)

                orig_img = (image * .2) + .5
                orig_img = orig_img[0][0].detach().cpu()

                # mask the black background pixels
                output_mask = np.ma.masked_where(output_cpu == 0, output_cpu)
                target_zero = np.ma.masked_where(target_zero == 0, target_zero)

                fig, (ax1, ax2, ax3) = plt.subplots(1, 3)
                ax1.imshow(orig_img, cmap='gray', vmin=0, vmax=1)
                ax1.set_title('input')
                ax1.axis('off')
                ax2.imshow(orig_img, cmap='gray', vmin=0, vmax=1)
                ax2.imshow(target_zero, cmap='cool', vmin=0, vmax=3, alpha=.3)
                ax2.set_title('ground-truth')
                ax2.tick_params(axis='both', labelsize=0, length=0)
                ax2.set(xlabel=("Defect Percentage: " + str(round(target_defect_percent, 5))))
                ax3.imshow(orig_img, cmap='gray', vmin=0, vmax=1)
                ax3.imshow(output_mask.squeeze(0), cmap='cool', vmin=0, vmax=3, alpha=.3)
                ax3.set_title('prediction')
                ax3.tick_params(axis='both', labelsize=0, length=0)
                ax3.set(xlabel=("Defect Percentage: " + str(round(output_defect_percent, 5))))
                fig.savefig(save_path + str(i) + '.png')
                # fig.show()
                plt.close('all')

            i += 1
            confmat.update(target.flatten(), output.flatten())

        confmat.reduce_from_all_processes()

        if visualize:
            # print classification report
            pred_class = pred_class[target_class != 128]
            target_class = target_class[target_class != 128]
            results = classification_report(target_class, pred_class, target_names=target_names)
            print(results)

    return confmat


def train_one_epoch(model, dice_loss, optimizer, data_loader, lr_scheduler, device, epoch, print_freq):
    model.train()
    metric_logger = utils.MetricLogger(delimiter="  ")
    metric_logger.add_meter('lr', utils.SmoothedValue(window_size=1, fmt='{value}'))
    header = 'Epoch: [{}]'.format(epoch)
    for image, target in metric_logger.log_every(data_loader, print_freq, header):
        image, target = image.to(device), target.to(device)
        output = model(image)
        loss = criterion(output, target)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        lr_scheduler.step()

        metric_logger.update(loss=loss, lr=optimizer.param_groups[0]["lr"])
        _, lss = metric_logger.get_meter()

    lss_str = str(lss)
    loss_split = lss_str.split()
    loss = float(loss_split[1].replace('(', '').replace(')', ''))

    return loss


def main(args):
    if args.output_dir:
        utils.mkdir(args.output_dir)

    utils.init_distributed_mode(args)
    print(args)
    args.epochs += 1
    args.start_epoch += 1

    device = torch.device(args.device)

    dataset = dataloader.BrainTumorSegmentationDataset(transform=get_transform(train=True),
                                                       folder_path=args.datadir + 'train/')
    dataset_val = dataloader.BrainTumorSegmentationDataset(transform=get_transform(train=False),
                                                           folder_path=args.datadir + 'val/')
    dataset_test = dataloader.BrainTumorSegmentationDataset(transform=get_transform(train=False),
                                                            folder_path=args.datadir + 'test/')

    if args.distributed:
        train_sampler = torch.utils.data.distributed.DistributedSampler(dataset)
        val_sampler = torch.utils.data.distributed.DistributedSampler(dataset_val)
        test_sampler = torch.utils.data.distributed.DistributedSampler(dataset_test)
    else:
        train_sampler = torch.utils.data.RandomSampler(dataset)
        val_sampler = torch.utils.data.SequentialSampler(dataset_val)
        test_sampler = torch.utils.data.SequentialSampler(dataset_test)

    data_loader = torch.utils.data.DataLoader(
        dataset, batch_size=args.batch_size,
        sampler=train_sampler, num_workers=args.workers,
        collate_fn=utils.collate_fn, drop_last=True)

    data_loader_val = torch.utils.data.DataLoader(
        dataset_val, batch_size=4,
        sampler=val_sampler, num_workers=args.workers,
        collate_fn=utils.collate_fn)

    data_loader_test = torch.utils.data.DataLoader(
        dataset_test, batch_size=1,
        sampler=test_sampler, num_workers=args.workers,
        collate_fn=utils.collate_fn)

    num_classes = args.num_classes
    class_weights = 0
    # only used if we want custom weighted loss function
    if args.class_weights:
        imgs = []
        for i in range(len(dataset)):
            imgs.append((dataset[i][1].flatten().numpy()))
        imagearr = np.asarray(imgs)
        image_array = imagearr[imagearr != 128]
        classes = np.unique(image_array)
        class_weights = class_weight.compute_class_weight(class_weight='balanced', classes=classes,
                                                          y=image_array)
        class_weights = [float(i) for i in class_weights]
        num_classes = np.size(classes)

    model = torch.hub.load('mateuszbuda/brain-segmentation-pytorch', 'unet',
                           in_channels=3, out_channels=1, init_features=32, pretrained=True)

    # not needed if unet model works
    # if args.model == 'deeplabv3_resnet50' or args.model == 'deeplabv3_resnet101':
    #     model.classifier = DeepLabHead(2048, num_classes)
    # else:
    #     num_ftrs_aux = model.aux_classifier[4].in_channels
    #     num_ftrs = model.classifier[4].in_channels
    #     model.aux_classifier[4] = nn.Conv2d(num_ftrs_aux, num_classes, kernel_size=1)
    #     model.classifier[4] = nn.Conv2d(num_ftrs, num_classes, kernel_size=1)

    # reshape for amount of classes
    num_ftrs = model.conv.in_channels
    model.conv = nn.Conv2d(num_ftrs, 4, kernel_size=1)
    # TODO: update to work with unet model
    model.to(device)

    if args.distributed:
        model = torch.nn.SyncBatchNorm.convert_sync_batchnorm(model)

    model_without_ddp = model
    if args.distributed:
        model = torch.nn.parallel.DistributedDataParallel(model, device_ids=[args.gpu])
        model_without_ddp = model.module

    # params_to_optimize = [
        # TODO: parameters to optimize
        # {"params": [p for p in model_without_ddp.backbone.parameters() if p.requires_grad]},
        # {"params": [p for p in model_without_ddp.classifier.parameters() if p.requires_grad]},
    # ]
    # if args.aux_loss:
        # params = [p for p in model_without_ddp.aux_classifier.parameters() if p.requires_grad]
        # params_to_optimize.append({"params": params, "lr": args.lr * 10})

    # optimizer = torch.optim.SGD(
    #     params_to_optimize,
    #     lr=args.lr, momentum=args.momentum, weight_decay=args.weight_decay)

    optimizer = torch.optim.Adam(model_without_ddp.parameters(), lr=args.lr)

    dice_loss = DiceLoss()

    lr_scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer,
        lambda x: (1 - x / (len(data_loader) * args.epochs)) ** 0.9)

    if args.resume:
        checkpoint = torch.load(args.resume, map_location='cpu')
        model_without_ddp.load_state_dict(checkpoint['model'], strict=not args.test_only)
        if not args.test_only:
            optimizer.load_state_dict(checkpoint['optimizer'])
            lr_scheduler.load_state_dict(checkpoint['lr_scheduler'])
            args.start_epoch = checkpoint['epoch'] + 1

    if args.test_only:
        confmat = evaluate(model, data_loader_test, device, num_classes, True, 999, 999)
        print(confmat)
        return

    start_time = time.time()
    result_dict = []
    loss_graph = []
    globalacc = []
    iou_nd = []
    iou_d = []
    meaniou = []
    best_loss = 5
    for epoch in range(args.start_epoch, args.epochs):
        if args.distributed:
            train_sampler.set_epoch(epoch)
        loss = train_one_epoch(model, dice_loss, optimizer, data_loader, lr_scheduler, device, epoch, args.print_freq)
        confmat = evaluate(model, data_loader_val, device, num_classes, False, epoch, args.epochs - 1)

        # save all results for analysis
        acc, _, iu = confmat.compute()
        loss_graph.append(loss)
        # result_dict.append(results)
        globalacc.append(acc.item() * 100)
        iou_nd.append((iu[0] * 100).item())
        iou_d.append((iu[1] * 100).item())
        meaniou.append(iu.mean().item() * 100)
        if epoch == (args.epochs - 1):
            data_dict = {"globalacc": globalacc, "meaniou": meaniou, "loss": loss_graph, "results": result_dict}
            with open(args.output_dir + 'data.txt', 'w') as file:
                json.dump(data_dict, file)

        print(confmat)
        checkpoint = {
            'model': model_without_ddp.state_dict(),
            'optimizer': optimizer.state_dict(),
            'lr_scheduler': lr_scheduler.state_dict(),
            'epoch': epoch,
            'args': args
        }
        pathlib.Path(args.output_dir.replace('.', './save_models')).mkdir(parents=True, exist_ok=True)
        utils.save_on_master(
            checkpoint,
            os.path.join(args.output_dir.replace('.', './save_models'), 'model_{}.pth'.format(epoch)))
        utils.save_on_master(
            checkpoint,
            os.path.join(args.output_dir, 'checkpoint.pth'))
        if loss < best_loss:
            best_loss = loss
            utils.save_on_master(checkpoint, os.path.join(args.output_dir, 'best_model.pth'))

    total_time = time.time() - start_time
    total_time_str = str(datetime.timedelta(seconds=int(total_time)))
    print('Training time {}'.format(total_time_str))

    if args.visualize:
        checkpoint = torch.load(os.path.join(args.output_dir, 'best_model.pth'), map_location='cpu')
        model.load_state_dict(checkpoint['model'], strict=not args.test_only)
        confmat = evaluate(model, data_loader_test, device, num_classes, True, epoch, args.epochs - 1)
        print(confmat)


def get_args_parser(add_help=True):
    import argparse
    parser = argparse.ArgumentParser(description='PyTorch Segmentation Training', add_help=add_help)

    parser.add_argument('--model', default='unet', help='model')
    parser.add_argument('--datadir', default='data/', help='image directory')
    parser.add_argument('--aux-loss', default=True, action='store_true', help='auxiliar loss')
    parser.add_argument('--device', default='cuda', help='device')
    parser.add_argument('--visualize', default=True, action='store_true', help='visualize output')
    parser.add_argument('--class-weights', action='store_true', help='weights for loss function')
    parser.add_argument('--num-classes', default=4, type=int, help='segmentation classes in dataset')
    parser.add_argument('--local_rank', default=0, type=int, help='distributed rank')
    parser.add_argument('-b', '--batch-size', default=16, type=int)
    parser.add_argument('--epochs', default=2, type=int, metavar='N', help='number of total epochs to run')
    parser.add_argument('-j', '--workers', default=8, type=int, metavar='N',
                        help='number of data loading workers (default: 16)')
    parser.add_argument('--lr', default=0.0005, type=float, help='initial learning rate')
    parser.add_argument('--momentum', default=0.9, type=float, metavar='M', help='momentum')
    parser.add_argument('--wd', '--weight-decay', default=1e-4, type=float,
                        metavar='W', help='weight decay (default: 1e-4)',
                        dest='weight_decay')
    parser.add_argument('--print-freq', default=10, type=int, help='print frequency')
    parser.add_argument('--output-dir', default='./Test/', help='path where to save')
    parser.add_argument('--resume', default='', help='resume from checkpoint')
    # parser.add_argument('--resume', default='', help='resume from checkpoint')
    parser.add_argument('--start-epoch', default=0, type=int, metavar='N', help='start epoch')
    parser.add_argument(
        "--test-only",
        default=False,
        dest="test_only",
        help="Only test the model",
        action="store_true",
    )
    parser.add_argument(
        "--pretrained",
        default=True,
        dest="pretrained",
        help="Use pre-trained models from the modelzoo",
        action="store_true",
    )
    # distributed training parameters
    parser.add_argument('--world-size', default=1, type=int,
                        help='number of distributed processes')
    parser.add_argument('--dist-url', default='env://', help='url used to set up distributed training')

    return parser


if __name__ == "__main__":
    args = get_args_parser().parse_args()
    main(args)
