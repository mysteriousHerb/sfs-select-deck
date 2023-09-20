# sfs-select-deck
Fork for the sfs-select to run on deck or other linux system, fork from https://www.unix-ag.uni-kl.de/~t_schmid/sfs-select/


### How to build
- `pipenv shell`
- `pyinstaller sfs-select.py --noconfirm --onefile --name sfs-select --icon="data/sfs-select.ico" `

### How to use
- in the first pop up window, paste the steam address, for steam deck this is `/home/deck/.local/share/Steam`
- Then it is self explanatary, refer to https://steamcommunity.com/groups/familysharing/discussions/1/3068621701744549116/

### For development
- clone the repo to your computer git clone 
- For steamdeck, install miniconda by https://docs.conda.io/projects/miniconda/en/latest/
- Install `pip install pipenv`
- Install the modules `pipenv install`
- Activate the pipenv environment `pipenv shell`
