# MRI_BrainTumor_Segmentation
About CAP 5516 Assignment #2, semantic segmentation of MRI scans of brain tumors using "a subset of the data used in the 2016 and 2017 Brain Tumour Image Segmentation (BraTS) challenges"

This code can be run by setting up an environment with the appropriate dependencies.

To run the code, the user simply needs to run the train.py python file*.

- In the command line, navigate to the appropriate directory, then type "python train.py". Or, run from a programming environment like PyCharm.
- Starting at line #339, the command line argument parser is found in train.py. The user can either chose to change these default values or use the appropriate commands while running.
- Example: to change the batch size from default 16 to 8, type "python train.py -b 8"


*NOTE: the dataset is not included in this GitHub repository. It needs to be installed from: https://drive.google.com/drive/folders/1HqEgzS8BV2c7xYNrZdEAnrHk7osJJ--2. The train-test-split was defined through the movement of files in the split.py script. The --datadir command line argument needs to point to your personal install location.
