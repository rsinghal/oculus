from django.shortcuts import render
from django.http import HttpResponse
from manifests import mets
from manifests import mods
from manifests import models
import json
import urllib2

# Create your views here.

METS_DRS_URL = "http://fds.lib.harvard.edu/fds/deliver/"
MODS_DRS_URL = "http://webservices.lib.harvard.edu/rest/MODS/via/"

# Returns a IIIF manifest of a METS document in the DRS
# Checks if DB has it, otherwise creates it
def manifest_mets(request, document_id):
    # Check if manifest exists
    has_manifest = models.manifest_exists(document_id)

    ## TODO: add last modified check

    if not has_manifest:
        # If not, get METS from DRS
        (success, mets) = get_mets(document_id)
        
        if not success:
            return mets # This is actually the 404 HttpResponse, so return and end the function
 
        # Convert to shared canvas model if successful
        converted_json = mets.main(mets, document_id)
        # Store to elasticsearch
        models.add_or_update_manifest(document_id, converted_json)
        
        response = HttpResponse(converted_json)
    else:
        # return JSON from db
        json_doc = models.get_manifest(document_id)
        response = HttpResponse(json.dumps(json_doc))
    
    add_headers(response)
    return response

# Returns a IIIF manifest of a MODS document in the DRS
# Checks if DB has it, otherwise creates it
def manifest_mods(request, document_id):
    pass

def delete(request, document_id):
    # Check if manifest exists
    has_manifest = models.manifest_exists(document_id)

    if has_manifest:
        models.delete_manifest(document_id)
        return HttpResponse("Document ID %s has been deleted" % document_id)
    else:
        return HttpResponse("Document ID %s does not exist in the database" % document_id, status=404)

# Force refresh a single document
# Pull METS, rerun conversion script, and store in db
def refresh_mets(request, document_id):
    (success, mets) = get_mets(document_id)

    if not success:
        return mets # This is actually the 404 HttpResponse, so return and end the function

    # Convert to shared canvas model if successful
    converted_json = mets.main(mets, document_id)

    # Store to elasticsearch
    models.add_or_update_manifest(document_id, converted_json)

    response = HttpResponse(converted_json)
    add_headers(response)
    return response

# Refresh a single document
# Pull MODS, rerun conversion script, store in db
def refresh_mods(request, document_id):
    pass

# Force refresh all originally METS documents in the db
# Might need to tweak so not hitting DRS as frequently 
# TODO: bulk load to elasticsearch
def refresh_mets_all(request):
    count = 0
    ids = models.get_all_manifest_ids()
    for document_id in ids:
        (success, mets) = get_mets(document_id)
        if not success:
            continue # don't need to keep processing because it doesn't exist in DRS
        count = count + 1
        converted_json = mets.main(mets, document_id)
        models.add_or_update_manifest(document_id, converted_json)

    return HttpResponse("Successfully refreshed %s of %s documents" % (count, len(ids)))

# Force refresh all originally MODS documents in the db
# Might need to tweak so not hitting DRS as frequently
# TODO: bulk load to elasticsesarch
def refresh_mods_all(request):
    pass

# Force refresh all documents in db (originally METS and MODS)
# Same issues as other refresh functions
def refresh_all(request):
    pass

## HELPER FUNCTIONS ##
def get_mets(document_id):
    mets_url = METS_DRS_URL+document_id
    try:
        response = urllib2.urlopen(mets_url)
    except urllib2.HTTPError, err:
        if err.code == 500:
            # document does not exist in DRS
            return (False, HttpResponse("The document ID %s does not exist" % document_id, status=404))

    mets = response.read()
    return (True, mets)

def get_mods(document_id):
    mods_url = MODS_DRS_URL+document_id
    try:
        response = urllib2.urlopen(mods_url)
    except urllib2.HTTPError, err:
        if err.code == 500:
            # document does not exist in DRS
            return (False, HttpResponse("The document ID %s does not exist" % document_id, status=404))

    mods = response.read()
    return (True, mods)

def add_headers(response):
    response["Access-Control-Allow-Origin"] = "*"
    response["Content-Type"] = "application/ld+json"
    return response
