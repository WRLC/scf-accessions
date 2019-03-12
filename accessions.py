import csv 
import time
import json    # not supported - create bib record
import os
import requests
import sys
import xml.etree.ElementTree as ET

#  Set up logging of progess and problems
#import logging
#from logging.config import fileConfig 
#fileConfig('logging_config.ini')
#logger = logging.getLogger()

#  Local keys and settings
from settings import *

UPDATE_IZ = 'scf' 
OWNING_IZ = sys.argv[1]
REPORT_FILE = sys.argv[2]
FROM_IZ_KEY = OWNING_IZ_KEYS[OWNING_IZ]
UPDATE_IZ_KEY = IZ_READ_WRITE_KEYS[UPDATE_IZ]
DEFAULT_LOCATION = DEFAULT_LOCATIONS[OWNING_IZ]
DEFAULT_LOC_DESC = DEFAULT_LOC_DESCS[OWNING_IZ]
SCF_LOC = ''
SCF_DESC = ''

#routes
GET_BY_BARCODE = '/almaws/v1/items?item_barcode={}'
GET_BIB_BY_NZ_MMS = '/almaws/v1/bibs?nz_mms_id={}'
GET_BIB_BY_MMS = '/almaws/v1/bibs?mms_id={}'
CREATE_BIB ='/almaws/v1/bibs?from_nz_mms_id={}'
GET_HOLDINGS_LIST='/almaws/v1/bibs/{mms_id}/holdings'
GET_HOLDING = '/almaws/v1/bibs/{mms_id}/holdings/{holding_id}'
CREATE_HOLDING = '/almaws/v1/bibs/{mms_id}/holdings'
GET_ITEMS_LIST = '/almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items'
CREATE_ITEM = '/almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items'

# setting up SCF vars to use
scf_get_params = {'apikey' : UPDATE_IZ_KEY}
scf_headers = {'Content-type': 'application/xml',
            'Authorization' : 'apikey ' + UPDATE_IZ_KEY}
scf_headers_apionly = {'Authorization' : 'apikey ' + UPDATE_IZ_KEY}

# HOLDINGS TEMPLATE - used to create holdings record for SCF
HOLDINGS_TEMPLATE = b'''<holding><record><leader>#####nx##a22#####1n#4500</leader><controlfield tag="008">1011252u####8###4001uueng0000000</controlfield><datafield ind1="0" ind2=" " tag="852"><subfield code="b">SCF</subfield><subfield code="c"></subfield><subfield code="h"></subfield><subfield code="i"></subfield></datafield></record></holding>'''

# Additional elements for records
EIGHT_FIVE_TWO_SUB_C = ".//record/datafield[@tag='852']/subfield[@code='c']"
EIGHT_FIVE_TWO_SUB_H = ".//record/datafield[@tag='852']/subfield[@code='h']"
EIGHT_FIVE_TWO_SUB_I = ".//record/datafield[@tag='852']/subfield[@code='i']"
TEMP_LOCATION = ".//holding_data/temp_location"
ITEM_DATA = ".//item_data"


def get_GT_location(loc):
    if (loc in ['ocs', 'ocwdc']):
        SCF_LOC = 'wrlc gtmo'
        SCF_DESC = 'WRLC GT Monographs'
    elif (loc == 'ocsk'):
        SCF_LOC = 'wrlc gtkib'
        SCF_DESC = 'WRLC GT Bioethics Mono'
    elif (loc == 'ocskp'):
        SCF_LOC = 'wrlc gtkip'
        SCF_DESC = 'WRLC GT Bioethics Per'
    elif (loc in ['ocsmr', 'ocswd']):
        SCF_LOC = 'wrlc gtspe'
        SCF_DESC = 'WRLC GT Spec Coll'
    elif (loc == 'ocsv'):
        SCF_LOC = 'wrlc gtv'
        SCF_DESC = 'WRLC GT Media Non Circ'
    elif (loc == 'ocsvc'):
        SCF_LOC = 'wrlc gtvc'
        SCF_DESC = 'WRLC GT Video Recording Circ'
    else:
        SCF_LOC = DEFAULT_LOCATION
        SCF_DESC = DEFAULT_LOC_DESC
    print('SCF_LOC in get = ', SCF_LOC)
    return [SCF_LOC, SCF_DESC]


def read_report_generator(report):
    cnt = 0
    with open(report) as fh:
        for barcode in fh:
#            print('\nbarcode = ', barcode)
            barcode = barcode.rstrip('\n')
#            logger.debug('BARCODE = %s', barcode)
            cnt += 1
            yield barcode 
    print('Number of barcodes read = ', cnt)
#    logger.info('Total number of barcodes read = %s', cnt)

def main():
    items_created = 0
    items_present = 0
    LogFile = UPDATE_IZ + 'ACC' + OWNING_IZ + 'log.' + time.strftime('%m%d%H%M', time.localtime())
    print ('LogFile = ', LogFile)
    print ('\nreport file = ', REPORT_FILE)
    for barcode in read_report_generator(REPORT_FILE):
        print('\nbarcode = ', barcode)

        # step one, retrieve by barcode
        r_owner_master_record = requests.get(ALMA_SERVER + GET_BY_BARCODE.format(barcode), params = {'apikey': FROM_IZ_KEY})

        if (r_owner_master_record.status_code != requests.codes.ok):
            print('Barcode not found.')
            # break from processing this barcode in  loop
            # log barcode with message for importer to check
            print('No match for barcode = ', barcode)
            continue

        print('\napikey for owner = ', FROM_IZ_KEY)

        owner_tree = r_owner_master_record.content

        print('\nrecord content = ', owner_tree)

        r_owner_master_record.url

        print('\nurl = ', r_owner_master_record.url)

#  Set up xml tree so we can parse for data 

        with open('test.xml', 'wb') as f:
            f.write (r_owner_master_record.content)

        tree = ET.parse('test.xml')
        root = tree.getroot()

#  Get item/bib_data/mms_id

        local_mms_id = root.find('./bib_data/mms_id').text
        print('\n local_mms_id = ', local_mms_id)

#  Get item/holding_data/holding_id & temp_location

        holding_id = root.find('./holding_data/holding_id').text
        print('\n holding id = ', holding_id)
        temp_location = root.find('./holding_data/temp_location').text
        temp_loc_desc = root.find('./holding_data/temp_location').get('desc') 
        if (temp_location is None):
            if ( OWNING_IZ ==  '4111' ):
                perm_loc = root.find('./item_data/location').text
                print('perm_loc = ', perm_loc)
                GTLoc = get_GT_location(perm_loc)
                temp_location = GTLoc[0] 
                temp_loc_desc = GTLoc[1]
            else:
                temp_location = DEFAULT_LOCATION
                temp_loc_desc = DEFAULT_LOC_DESC
        print('\n temp location = ', temp_location)
        print('\n tmp loc desc = ', temp_loc_desc)

#  Get item/item_data/pid
        pid = root.find('./item_data/pid').text
        print('\n pid = ', pid)

#  Get the physical_material_type - need to check later
        physical_material_type = root.find('./item_data/physical_material_type').text
        print('\n physical_material_type = ', physical_material_type)

#  Create new item record but remove pid and physical_material_type if necesary
        new_item_record = ET.fromstring(b'<item></item>')
        item_data = tree.find('./item_data')
        pid_element = item_data.find('pid')
        item_data.remove(pid_element)

        library_element = item_data.find('library')
        library_element.text = 'SCF'
        library_element.set('desc', 'WRLC - Shared Collections Facility')

        print('lib_ele desc = ', library_element.text)

#  Do I need to get the description of location in real time?  Perhaps a look up table will do
        location_element = item_data.find('location')
        location_element.text = temp_location
        if (location_element != ''):
            location_element.set('desc', temp_loc_desc)

#  Made the assumption that policy will be regular/circ.  Perhaps make this a calling parameter of the script in the future.  That would take care of periodicals and non-cirulating things.
##  Can we map some basic policies or is this okay?
        policy_element = item_data.find('policy')
        policy_element.text = 'circ'
        policy_element.set('desc', 'regular')

#  Perhaps do more mapping of material type to Item policy above (ISSUE=perl?)
        if physical_material_type == 'ELEC':
            for physical_material_type in item_data.iter('physical_material_type'):
                physical_material_type.text = str('OTHER')
                physical_material_type.set('desc', 'Other')
                print('Check material type for BC =', barcode)
        new_item_record.append(item_data)
        ET.dump(new_item_record)

#  Get item/bib_data/network_numbers/network_number from WRLC NZ

        nz_mms_id = 0
        for item in root.findall('./bib_data/network_numbers/network_number'):
            print ('\n NZ_mms_id = ', item.text)
            if (item.text).find('WRLC_NETWORK') != -1:
                print('\ngood one = ', item.text[22:])
                nz_mms_id = item.text[22:]

#  Check that NZ bib exists, if not stop and report
        if (nz_mms_id == 0):
            print('No NZ Bib record for barcode = ', barcode)
            continue


#  Search for bib in SCF given the network zone mms_id
        scf_mms_id = 0
        r_scf_bib = requests.get(ALMA_SERVER + GET_BIB_BY_NZ_MMS.format(nz_mms_id), params=scf_get_params)

        if (r_scf_bib.status_code == requests.codes.ok):
            # We have a bib record in scf
            r_scf_bib.content
            scf_bib_content = ET.fromstring(r_scf_bib.content)
            scf_mms_id = scf_bib_content.find('./bib/mms_id').text
            print('\n scf_mms_id = ', scf_mms_id)
            print('\n scf bib record = ', r_scf_bib.url)
        else:

#  Create a bib record for scf    
            empty_bib = b'<bib />'
            r_create_bib = requests.post(ALMA_SERVER + CREATE_BIB.format(nz_mms_id), headers=scf_headers, data=empty_bib) 

            r_create_bib.content
            scf_bib_create_content = ET.fromstring(r_create_bib.content)
            scf_mms_id = scf_bib_create_content.find('./bib/mms_id').text

            print('newly created mms_id = ', scf_mms_id)

#  Need to check if there is a holding record with item's location in SCF

        r_scf_holding = requests.get(ALMA_SERVER + GET_HOLDINGS_LIST.format(mms_id=scf_mms_id), params=scf_get_params)
        print('holdings url = ', r_scf_holding.url)
        scf_hold_list = ET.fromstring(r_scf_holding.content)

#  Need to interate through list, search for location match to get holding_id
        scf_holding_id = 0
        for child in scf_hold_list:
            if (child.tag == 'holding'):
                print('under holding')
                print('temp loc = ', temp_location)
                if (child.find('location').text == temp_location):
                    print(child.find('holding_id').text)
                    scf_holding_id = child.find('holding_id').text
                    break


#  Get holding information from local IZ if not present in SCF
        if (scf_holding_id == 0):
            r_local_holding = requests.get(ALMA_SERVER + GET_HOLDING.format(mms_id=local_mms_id ,holding_id=holding_id), params={'apikey': FROM_IZ_KEY})
            local_holding = r_local_holding.content
            print('\n local holding = ', local_holding)
 
            # parse owning holdings record
            owning_holdings_record = ET.fromstring(local_holding)

            # extract 852 information
            eight52_h = owning_holdings_record.find(EIGHT_FIVE_TWO_SUB_H).text
            if (owning_holdings_record.find(EIGHT_FIVE_TWO_SUB_I) is None):
                eight52_i = str('')
            else: 
                eight52_i = owning_holdings_record.find(EIGHT_FIVE_TWO_SUB_I).text

            print(eight52_h)
            print(eight52_i)

            print(temp_location)

            # Create empty holding record from template
            new_holdings_record = ET.fromstring(HOLDINGS_TEMPLATE)

            # Now insert the owning call number
            new_holdings_record.find(EIGHT_FIVE_TWO_SUB_H).text = eight52_h
            new_holdings_record.find(EIGHT_FIVE_TWO_SUB_I).text = eight52_i
            new_holdings_record.find(EIGHT_FIVE_TWO_SUB_C).text = temp_location

            ET.dump(new_holdings_record)

            payload = ET.tostring(new_holdings_record, encoding='utf-8')
            print('\nnew holdings payload = ', payload)

#  Create/Post the new holding record in the SCF    ##### Uncomment
            new_holding =''
            new_holding = requests.post(ALMA_SERVER + CREATE_HOLDING.format(mms_id=scf_mms_id), headers=scf_headers, data=payload)
            if (new_holding.status_code == requests.codes.ok):
                print('\nnew hold content = ', new_holding.content)

                new_scf_hold_record = ET.fromstring(new_holding.content)
                scf_holding_id = new_scf_hold_record.find('holding_id').text
                print('new scf_holding_id = ', scf_holding_id)
            else:
                print('did not create holding record, maybe there was a holding record')
                continue

#  End if no holdings that match in SCF

#  At this point we should have a scf bib and a location matching holding record

#  Check to see if item has already been created

        scf_item_record = requests.get(ALMA_SERVER + GET_ITEMS_LIST.format(mms_id=scf_mms_id, holding_id=scf_holding_id), params=scf_get_params)

        scf_item_list = ET.fromstring(scf_item_record.content)
        print('\n\n')
        ET.dump(scf_item_list)
        print('\n\n')

#  Need to interate through list to see if there is an item record.  If empty,
#  Need to create the item.  If not, do we need to update??
#####  Do we need sleep?  I know I do.  Do we need to update the item record?
        item_exists = 0
        for child in scf_item_list.iter('barcode'):
#            time.sleep(5)
            print('in the list')
            print(child.text)
            if (child.text  == barcode):
                print('item is already in SCF')
                print(barcode, ' does not need to be added.\n')
                item_exists = 1     # flag
                items_present += 1  # counter
                break


#  Create the new item record in the SCF
        if (item_exists == 0):
            payload = ET.tostring(new_item_record, encoding='utf-8')
            print('\nnew item record = ', payload)

            new_scf_item = requests.post(ALMA_SERVER + CREATE_ITEM.format(mms_id=scf_mms_id, holding_id=scf_holding_id), headers=scf_headers, data=payload)

            if (new_scf_item.status_code != requests.codes.ok):
                print('A new item was not created ')
                items_present += 1
            else:
                new_scf_item_record = ET.fromstring(new_scf_item.content)
                items_created += 1

#  Need to test for correct submission
#  if correct increment counter
#  This should be end of processing - continue the loop.

#  Report at end
    print('Items created = ', items_created)
    print('Items already present = ', items_present)


if __name__ == '__main__':
    main()
