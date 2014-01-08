from django.shortcuts import render
from django.http import HttpResponse
from .models import get_manifest, manifest_exists, add_or_update_manifest, delete_manifest
import json
import urllib2
#from .harvard-converter import main
from manifests import hc
from manifests import test

# Create your views here.

def manifest(request, document_id):
    # Check if manifest exists
    has_manifest = manifest_exists(document_id)

    ## TODO: add last modified check

    if not has_manifest:
        # If not, get METS from DRS
        mets_url = "http://fds.lib.harvard.edu/fds/deliver/"+document_id
        try:
            response = urllib2.urlopen(mets_url)
        except urllib2.HTTPError, err:
            if err.code == 500:
                # document does not exist in DRS
                return HttpResponse("The document ID %s does not exist" % document_id, status=404)

        mets = response.read()

        # Convert to shared canvas model
        converted_json = hc.main(mets, document_id)
        # Store to elasticsearch
        add_or_update_manifest(document_id, converted_json)

    #return JSON
    json_doc = get_manifest(document_id)
    
    return HttpResponse(json.dumps(json_doc), content_type="application/json")

def delete(request, document_id):
    # Check if manifest exists
    has_manifest = manifest_exists(document_id)

    if has_manifest:
        delete_manifest(document_id)
        return HttpResponse("Document ID %s has been deleted" % document_id)
    else:
        return HttpResponse("Document ID %s does not exist in the database" % document_id, status=404)
