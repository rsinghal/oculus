from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from manifests import mets
from manifests import mods
from manifests import models
import json
import urllib2

# Create your views here.

METS_DRS_URL = "http://fds.lib.harvard.edu/fds/deliver/"
MODS_DRS_URL = "http://webservices.lib.harvard.edu/rest/MODS/via/"

# view one or more mets object in mirador
def view_mets(request, document_id):
    doc_ids = document_id.split(";")
    manifests = {}
    for doc_id in doc_ids:
        (success, response) = get_mets_manifest(doc_id)
        if success:
            title = models.get_manifest_title(doc_id)
            uri = "/manifests/mets/"+doc_id # TODO: fix
            manifests[uri] = title

    if len(manifests) > 0:
        return render(request, 'manifests/manifest.html', {'manifests' : manifests})
    else:
        return HttpResponse("The requested document ID(s) %s could not be displayed" % document_id, status=404) # 404 HttpResponse object

# view one or more mods object in mirador
def view_mods(request, document_id):
    doc_ids = document_id.split(";")
    manifests = {}
    for doc_id in doc_ids:
        (success, response) = get_mods_manifest(doc_id)
        if success:
            title = models.get_manifest_title(doc_id)
            uri = "http://localhost:8000/manifests/mods/"+doc_id
            manifests[uri] = title

    if len(manifests) > 0:
        return render(request, 'manifests/manifest.html', {'manifests' : manifests})
    else:
        return HttpResponse("The requested document ID(s) %s could not be displayed" % document_id, status=404) # 404 HttpResponse object

# Returns a IIIF manifest of a METS document in the DRS
# Checks if DB has it, otherwise creates it
def manifest_mets(request, document_id):
    (success, response_doc) = get_mets_manifest(document_id)
    if success:
        response = HttpResponse(response_doc)
        add_headers(response)
        return response
    else:
        return response_doc # 404 HttpResponse

# Returns a IIIF manifest of a MODS document in the DRS
# Checks if DB has it, otherwise creates it
def manifest_mods(request, document_id):
    (success, response_doc) = get_mods_manifest(document_id)
    if success:
        response = HttpResponse(response_doc)
        add_headers(response)
        return response
    else:
        return response_doc # 404 HttpResponse

# Delete any document from db
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
    (success, response) = get_mets(document_id)

    if not success:
        return response # This is actually the 404 HttpResponse, so return and end the function

    # Convert to shared canvas model if successful
    converted_json = mets.main(response, document_id)

    # Store to elasticsearch
    models.add_or_update_manifest(document_id, converted_json)

    http_response = HttpResponse(converted_json)
    add_headers(http_response)
    return http_response

# Refresh a single document
# Pull MODS, rerun conversion script, store in db
def refresh_mods(request, document_id):
    (success, response) = get_mods(document_id)
    if not success:
        return response
    
    converted_json = mods.main(response, document_id)
    models.add_or_update_manifest(document_id, converted_json)
    http_response = HttpResponse(converted_json)
    add_headers(http_response)
    return http_response

# this is a hack because the javascript uses relative paths for the PNG files, and Django creates the incorrect URL for them
# Need to find a better and more permanent solution
def get_image(request, filename):
    return HttpResponseRedirect("/static/manifests/images/openseadragon/%s" % filename)

## HELPER FUNCTIONS ##
# Gets METS XML from DRS
def get_mets(document_id):
    mets_url = METS_DRS_URL+document_id
    try:
        response = urllib2.urlopen(mets_url)
    except urllib2.HTTPError, err:
        if err.code == 500 or err.code == 404:
            # document does not exist in DRS, might need to add more error codes
            return (False, HttpResponse("The document ID %s does not exist" % document_id, status=404))

    response_doc = response.read()
    return (True, response_doc)

# Gets MODS XML from Presto API
def get_mods(document_id):
    mods_url = MODS_DRS_URL+document_id
    try:
        response = urllib2.urlopen(mods_url)
    except urllib2.HTTPError, err:
        if err.code == 500: ## TODO
            # document does not exist in DRS
            return (False, HttpResponse("The document ID %s does not exist" % document_id, status=404))

    mods = response.read()
    return (True, mods)

# Adds headers to Response for returning JSON that other Mirador instances can access
def add_headers(response):
    response["Access-Control-Allow-Origin"] = "*"
    response["Content-Type"] = "application/ld+json"
    return response

# Uses other helper methods to create JSON
def get_mets_manifest(document_id):
    # Check if manifest exists
    has_manifest = models.manifest_exists(document_id)

    ## TODO: add last modified check

    if not has_manifest:
        # If not, get METS from DRS
        (success, response) = get_mets(document_id)
        
        if not success:
            return (success, response) # This is actually the 404 HttpResponse, so return and end the function
 
        # Convert to shared canvas model if successful
        converted_json = mets.main(response, document_id)
        # Store to elasticsearch
        models.add_or_update_manifest(document_id, converted_json)        
        return (success, converted_json)
    else:
        # return JSON from db
        json_doc = models.get_manifest(document_id)
        return (True, json.dumps(json_doc))

# Uses other helper methods to create JSON
def get_mods_manifest(document_id):
    # Check if manifest exists
    has_manifest = models.manifest_exists(document_id)

    ## TODO: add last modified check

    if not has_manifest:
        # If not, get MODS from DRS
        (success, response) = get_mods(document_id)
        
        if not success:
            return (success, response) # This is actually the 404 HttpResponse, so return and end the function
 
        # Convert to shared canvas model if successful
        converted_json = mods.main(response, document_id)
        # Store to elasticsearch
        models.add_or_update_manifest(document_id, converted_json)        
        return (success, converted_json)
    else:
        # return JSON from db
        json_doc = models.get_manifest(document_id)
        return (True, json.dumps(json_doc))
