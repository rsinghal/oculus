from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from manifests import mets
from manifests import mods
from manifests import models
import json
import urllib2

# Create your views here.

METS_DRS_URL = "http://fds.lib.harvard.edu/fds/deliver/"
METS_API_URL = "http://pds.lib.harvard.edu/pds/get/"
MODS_DRS_URL = "http://webservices.lib.harvard.edu/rest/MODS/"

sources = {"drs": "mets", "via": "mods", "hollis": "mods"}

# view any number of MODS or METS objects
def view(request, document_id):
    doc_ids = document_id.split(';')
    manifests = {}
    for doc_id in doc_ids:
        parts = doc_id.split(':')
        if len(parts) != 2:
            continue # not a valid id, don't display
        source = parts[0]
        id = parts[1]
        #print source, id
        (success, response, real_id, real_source) = get_manifest(id, source, False)
        if success:
            title = models.get_manifest_title(real_id, real_source)
            uri = "/manifests/"+real_source+":"+real_id
            manifests[uri] = title

    if len(manifests) > 0:
        return render(request, 'manifests/manifest.html', {'manifests' : manifests})
    else:
        return HttpResponse("The requested document ID(s) %s could not be displayed" % document_id, status=404) # 404 HttpResponse object

# Returns a IIIF manifest of a METS or MODS document in DRS
# Checks if DB has it, otherwise creates it
def manifest(request, document_id):
    parts = document_id.split(":")
    if len(parts) != 2:
        return HttpResponse("Invalid document ID. Format: [data source]:[ID]", status=404)
    source = parts[0]
    id = parts[1]
    (success, response_doc, real_id, real_source) = get_manifest(id, source, False)
    if success:
        response = HttpResponse(response_doc)
        add_headers(response)
        return response
    else:
        return response_doc # 404 HttpResponse
            
# Delete any document from db
def delete(request, document_id):
    # Check if manifest exists
    parts = document_id.split(":")
    if len(parts) != 2:
        return HttpResponse("Invalid document ID. Format: [data source]:[ID]", status=404)
    source = parts[0]
    id = parts[1]
    has_manifest = models.manifest_exists(id, source)

    if has_manifest:
        models.delete_manifest(id, source)
        return HttpResponse("Document ID %s has been deleted" % document_id)
    else:
        return HttpResponse("Document ID %s does not exist in the database" % document_id, status=404)

# Force refresh a single document
# Pull METS or MODS, rerun conversion script, and store in db
def refresh(request, document_id):
    parts = document_id.split(":")
    if len(parts) != 2:
        return HttpResponse("Invalid document ID. Format: [data source]:[ID]", status=404)
    source = parts[0]
    id = parts[1]
    (success, response_doc, real_id, real_source) = get_manifest(id, source, True)

    if success:
        response = HttpResponse(response_doc)
        add_headers(response)
        return response
    else:
        return response_doc # This is actually the 404 HttpResponse, so return and end the function

# this is a hack because the javascript uses relative paths for the PNG files, and Django creates the incorrect URL for them
# Need to find a better and more permanent solution
def get_image(request, filename):
    return HttpResponseRedirect("/static/manifests/images/openseadragon/%s" % filename)

## HELPER FUNCTIONS ##
# Gets METS XML from DRS
def get_mets(document_id, source):
    mets_url = METS_DRS_URL+document_id
    try:
        response = urllib2.urlopen(mets_url)
    except urllib2.HTTPError, err:
        if err.code == 500 or err.code == 404:
            # document does not exist in DRS, might need to add more error codes
            return (False, HttpResponse("The document ID %s does not exist" % document_id, status=404))

    response_doc = response.read()
    return (True, response_doc)

def mets_jp2_check(document_id):
    api_url = METS_API_URL+document_id
    response = urllib2.urlopen(api_url)
    response_doc = response.read()
    # probably don't actually need to parse this as an XML document
    # just look for this particular string in the response
    if "<img_mimetype>jp2</img_mimetype>" in response_doc:
        return True
    else:
        return False

# Gets MODS XML from Presto API
def get_mods(document_id, source):
    mods_url = MODS_DRS_URL+source+"/"+document_id
    #print mods_url
    try:
        response = urllib2.urlopen(mods_url)
    except urllib2.HTTPError, err:
        if err.code == 500 or err.code == 403: ## TODO
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
def get_manifest(document_id, source, force_refresh):
    # Check if manifest exists
    has_manifest = models.manifest_exists(document_id, source)

    ## TODO: add last modified check

    if not has_manifest or force_refresh:
        # If not, get MODS or METS from DRS
        xml_type = sources[source]
        if xml_type == "mods":
            ## TODO: check image types??
            (success, response) = get_mods(document_id, source)
        elif xml_type == "mets":
            # check if mets object has jp2 images, only those will work in image server
            has_jp2 = mets_jp2_check(document_id)
            if not has_jp2:
                return (has_jp2, HttpResponse("The document ID %s does not have JP2 images" % document_id, status=404))
            
            (success, response) = get_mets(document_id, source)
        else:
            success = False
            response = HttpResponse("Invalid source type", status=404)

        if not success:
            return (success, response) # This is actually the 404 HttpResponse, so return and end the function
 
        # Convert to shared canvas model if successful
        if xml_type == "mods":
            converted_json = mods.main(response, document_id)
            # check if this is, in fact, a PDS object masked as a hollis request
            # If so, get the manifest with the DRS METS ID and return that
            json_doc = json.loads(converted_json)
            if 'pds' in json_doc:
                id = json_doc['pds']
                return get_manifest(id, 'drs', False)
        elif xml_type == "mets":
            converted_json = mets.main(response, document_id)
        else:
            pass
        # Store to elasticsearch
        models.add_or_update_manifest(document_id, converted_json, source)
        # Return the docuemnt_id and source in case this is a hollis record
        # that also has METS/PDS
        return (success, converted_json, document_id, source)
    else:
        # return JSON from db
        json_doc = models.get_manifest(document_id, source)
        return (True, json.dumps(json_doc), document_id, source)
