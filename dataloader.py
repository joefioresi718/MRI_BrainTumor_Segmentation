from __future__ import print_function, division
import os
from PIL import Image
import glob2 as glob
from torch.utils.data import Dataset


class BrainTumorSegmentationDataset(Dataset):
    def __init__(self, folder_path, transform):
        self.transform = transform
        self.img_files = glob.glob(os.path.join(folder_path, 'images/*'))
        self.label_files = []
        for img_path in self.img_files:
            self.label_files.append(os.path.join(img_path.replace('images', 'labels')))

    def __getitem__(self, index):
        image = Image.open(self.img_files[index])
        label = Image.open(self.label_files[index])
        image, label = self.transform(image, label)
        return image, label

    def __len__(self):
        return len(self.img_files)

    # def __init__(self, folder_path, transform):
    #     # super(BrainTumorSegmentationDataset, self).__init__()
    #     self.transform = transform
    #     self.img_files = glob.glob(os.path.join(folder_path, 'images/', '*.nii.gz'))
    #     self.mask_files = []
    #     for img_path in self.img_files:
    #         self.mask_files.append(os.path.join(img_path.replace('images', 'labels')))
    #
    # def __getitem__(self, index):
    #     image = np.array(nib.load(self.img_files[int(index/155)]).dataobj)
    #     label = np.array(nib.load(self.mask_files[int(index/155)]).dataobj)
    #     image = Image.fromarray(image[:, :, index % 155, 0].astype('uint8')).convert('RGB')
    #     label = Image.fromarray(label[:, :, index % 155].astype('uint8'))
    #     image, label = self.transform(image, label)
    #     return image, label
    #
    # def __len__(self):
    #     return len(self.img_files*155)

