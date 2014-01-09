from django.shortcuts import render
from django.http import HttpResponse
from manifests import hc
from manifests import models
import json
import urllib2

# Create your views here.

DRS_URL = "http://fds.lib.harvard.edu/fds/deliver/"

def manifest(request, document_id):
    # Check if manifest exists
    has_manifest = models.manifest_exists(document_id)

    ## TODO: add last modified check

    if not has_manifest:
        # If not, get METS from DRS
        (success, mets) = get_mets(document_id)
        
        if not success:
            return mets # This is actually the 404 HttpResponse, so return and end the function
 
        # Convert to shared canvas model if successful
        converted_json = hc.main(mets, document_id)
        # Store to elasticsearch
        models.add_or_update_manifest(document_id, converted_json)
        
        response = HttpResponse(converted_json, content_type="application/json")
    else:
        # return JSON from db
        json_doc = models.get_manifest(document_id)
        response = HttpResponse(json.dumps(json_doc), content_type="application/json")
    
    response["Access-Control-Allow-Origin"] = "*"
    return response

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
def refresh(request, document_id):
    (success, mets) = get_mets(document_id)

    if not success:
        return mets # This is actually the 404 HttpResponse, so return and end the function

    # Convert to shared canvas model if successful
    converted_json = hc.main(mets, document_id)

    # Store to elasticsearch
    models.add_or_update_manifest(document_id, converted_json)

    response = HttpResponse(converted_json, content_type="application/json")
    response["Access-Control-Allow-Origin"] = "*"
    return response

# Force refresh all document in the db
# Might need to tweak so not hitting DRS too frequently 
# and bulk load to elasticsearch
def refresh_all(request):
    count = 0
    ids = models.get_all_manifest_ids()
    for document_id in ids:
        (success, mets) = get_mets(document_id)
        if not success:
            continue # don't need to keep processing because it doesn't exist in DRS
        count = count + 1
        converted_json = hc.main(mets, document_id)
        models.add_or_update_manifest(document_id, converted_json)

    return HttpResponse("Successfully refreshed %s of %s documents" % (count, len(ids)))

## HELPER FUNCTIONS ##
def get_mets(document_id):
    mets_url = DRS_URL+document_id
    try:
        response = urllib2.urlopen(mets_url)
    except urllib2.HTTPError, err:
        if err.code == 500:
            # document does not exist in DRS
            return (False, HttpResponse("The document ID %s does not exist" % document_id, status=404))

    mets = response.read()
    return (True, mets)
