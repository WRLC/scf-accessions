import csv 
import json    # not supported - create bib record
import os
import requests
import sys
import xml.etree.ElementTree as ET

from settings import *

UPDATE_IZ = 'scf' 
OWNING_IZ = sys.argv[1]
REPORT_FILE = sys.argv[2]
FROM_IZ_KEY = OWNING_IZ_KEYS[OWNING_IZ]
UPDATE_IZ_KEY = IZ_READ_WRITE_KEYS[UPDATE_IZ]

#routes
GET_BY_BARCODE = '/almaws/v1/items?item_barcode={}'
GET_BIB_BY_NZ_MMS = '/almaws/v1/bibs?nz_mms_id={}'
GET_BIB_BY_MMS = '/almaws/v1/bibs?mms_id={}'
CREATE_BIB ='/almaws/v1/bibs?from_nz_mms_id={}'
GET_HOLDING = '/almaws/v1/bibs/{mms_id}/holdings/{holding_id}'
CREATE_HOLDING = '/almaws/v1/bibs/{mms_id}/holdings'
CREATE_ITEM = '/almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items'

# setting up SCF vars to use
scf_get_params = {'apikey' : UPDATE_IZ_KEY}
scf_headers = {'Content-type': 'application/xml',
            'Authorization' : 'apikey ' + UPDATE_IZ_KEY}
scf_headers_apionly = {'Authorization' : 'apikey ' + UPDATE_IZ_KEY}

# HOLDINGS TEMPLATE - used to create holdings record for SCF
HOLDINGS_TEMPLATE = b'''
<holding><record><leader>#####nx##a22#####1n#4500</leader><controlfield tag="008">1011252u####8###4001uueng0000000</controlfield><datafield ind1="0" ind2=" " tag="852"><subfield code="b">SCF</subfield><subfield code="c"></subfield><subfield code="h"></subfield><subfield code="i"></subfield></datafield></record></holding>'''

# Additional elements for records
EIGHT_FIVE_TWO_SUB_C = ".//record/datafield[@tag='852']/subfield[@code='c']"
EIGHT_FIVE_TWO_SUB_H = ".//record/datafield[@tag='852']/subfield[@code='h']"
EIGHT_FIVE_TWO_SUB_I = ".//record/datafield[@tag='852']/subfield[@code='i']"
TEMP_LOCATION = ".//holding_data/temp_location"
ITEM_DATA = ".//item_data"


def alma_get(resource, apikey, params=None, fmt='json'):
    '''
    makes a generic alma api call, pass in a resource
    '''
    params = params or {}
    params['apikey'] = apikey
    params['format'] = fmt
    r = requests.get(resource, params=params) 
    r.raise_for_status()
    return r

def alma_put(resource, apikey, payload=None, params=None, fmt='json'):

    '''
    makes a generic post request to alma api.
    '''
    payload = payload or {}
    params = params or {}
    params['format'] = fmt
    headers =  {
        'Content-type': 'application/{fmt}'.format(fmt=fmt),
        'Authorization' : 'apikey ' + apikey,
    }
    r = requests.put(resource,
                     headers=headers,
                     params=params,
                     data=payload)
    r.raise_for_status()
    return r

def read_report_generator(report):
    cnt = 0
    with open(report) as fh:
        for barcode in fh:
            print('\nbarcode = ', barcode)
            barcode = barcode.rstrip('\n')
            cnt += 1
            yield barcode 
    print('\nnumber of barcodes = ', cnt)

def main():
    count_all_records = 0
    print ('\nreport file = ', REPORT_FILE)
    print('\nscf iz key =', UPDATE_IZ_KEY)
    for barcode in read_report_generator(REPORT_FILE):
        print('\nbarcode = ', barcode)

        # step one, retrieve by barcode
        r_owner_master_record = requests.get(ALMA_SERVER + GET_BY_BARCODE.format(barcode), params = {'apikey': FROM_IZ_KEY})

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

        mms_id = root.find('./bib_data/mms_id').text
        print('\n local mms_id = ', mms_id)

#  Get item/holding_data/holding_id & temp_location

        holding_id = root.find('./holding_data/holding_id').text
        print('\n holding id = ', holding_id)
        temp_location = root.find('./holding_data/temp_location').text
        print('\n temp location = ', temp_location)

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
        if physical_material_type == 'ELEC':
            for physical_material_type in item_data.iter('physical_material_type'):
                physical_material_type.text = str('')
        new_item_record.append(item_data)
        ET.dump(new_item_record)

#  Get item/bib_data/network_numbers/network_number from WRLC NZ

        for item in root.findall('./bib_data/network_numbers/network_number'):
            print ('\n mms_id = ', item.text)
            if (item.text).find('WRLC_NETWORK') != -1:
                print('\ngood one = ', item.text[22:])
                nz_mms_id = item.text[22:]



#  Search for bib in SCF given the network zone mms_id
        r_scf_bib = requests.get(ALMA_SERVER + GET_BIB_BY_NZ_MMS.format(nz_mms_id), params=scf_get_params)

        print('\nbib info from SCF = ', r_scf_bib.content)

        if (r_scf_bib.status_code == requests.codes.ok):
            # We have a bib record in scf
            r_scf_bib.content
            print('\n scf bib record = ', r_scf_bib.url)
        else:
            #We need to get/create a bib record from the local IZ
            r_local_bib = requests.get(ALMA_SERVER + GET_BIB_BY_MMS.format(mms_id), params={'apikey': FROM_IZ_KEY})

            local_bib = r_local_bib.content
            print('\n local bib = ', local_bib)

#  TO DO:  create a bib record for scf from the local bib above
            empty_bib = b'<bib />'
#            r_create_bib = requests.post(ALMA_SERVER + CREATE_BIB.format(nz_mms_id), headers=scf_headers, data=empty_bib)  # leave nz_mms_id empty when creating a regular local record.

#            r_create_bib.content
#            created_bib=r_create_bib.content
#            print('added bib response = ', created_bib)

#  Create holding - first search for local holding record, then create

        r_local_holding = requests.get(ALMA_SERVER + GET_HOLDING.format(mms_id=mms_id ,holding_id=holding_id), params={'apikey': FROM_IZ_KEY})
        local_holding = r_local_holding.content
        print('\n local holding = ', local_holding)

#  TO DO:  create holding record for scf from local holding above

        # parse owning holdings record
        owning_holdings_record = ET.fromstring(local_holding)

        # extract 852 information
        eight52_h = owning_holdings_record.find(EIGHT_FIVE_TWO_SUB_H).text
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

        #  Post new holding to SCF
        payload = ET.tostring(new_holdings_record, encoding='utf-8')
        print('\npayload = ', payload)

        # Create the new holding record in the SCF
#        new_holding = requests.post(ALMA_SERVER + CREATE_HOLDING.format(mms_id=mms_id), headers=scf_headers, data=payload)
#        print('\nnew hold content = ', new_holding.content)

        # Create the new item record in the SCF
        payload = ET.tostring(new_item_record, encoding='utf-8')
        print('\nnew item record = ', payload)

#        new_scf_item = requests.post(ALMA_SERVER + CREATE_ITEM.format(mms_id=mms_id, holding_id=holding_id), headers=scf_headers, data=payload)
#        print('\nresponse to posting new item in scf = ', new_scf_item.content)

if __name__ == '__main__':
    main()
