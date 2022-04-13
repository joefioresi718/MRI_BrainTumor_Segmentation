# MRI_BrainTumor_Segmentation
About CAP 5516 Assignment #2, semantic segmentation of MRI scans of brain tumors using "a subset of the data used in the 2016 and 2017 Brain Tumour Image Segmentation (BraTS) challenges"

This code can be run by setting up an environment with the appropriate dependencies.

To run the code, the user simply needs to run the train.py python file*.

- In the command line, navigate to the appropriate directory, then type "python -m torch.distributed.launch --nproc_per_node=2 --master_port 20003 train.py".
- This code required 2 GPUS in order to run

*NOTE: the dataset is not included in this GitHub repository. It needs to be installed from: https://drive.google.com/drive/folders/1HqEgzS8BV2c7xYNrZdEAnrHk7osJJ--2. 

