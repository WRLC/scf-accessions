# scf-accessions
Batch job to accession barcodes into the SCF

#set up a virtual environment
python3 -m venv venv
source venv/bin/activate

# install the module and requirements
pip install -r requirements.txt

# to run script
python accessions.py 4105 test1.txt
