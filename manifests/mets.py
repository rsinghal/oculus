#!/usr/bin/python

from lxml import etree
import json, sys
import urllib2

metsNS = 'http://www.loc.gov/METS/'
modsNS = 'http://www.loc.gov/mods/v3'
xlinkNS = 'http://www.w3.org/1999/xlink'
premisNS ="info:lc/xmlns/premis-v2"
hulDrsAdminNS ="http://hul.harvard.edu/ois/xml/ns/hulDrsAdmin"

ALLNS = {'mets':metsNS, 'mods':modsNS, 'xlink':xlinkNS, 'premis':premisNS, 'hulDrsAdmin':hulDrsAdminNS}
imageHash = {}
canvasInfo = []
rangesJsonList = []

## TODO: Other image servers?
imageUriBase = "https://images.harvardx.harvard.edu/ids/iiif/"
imageUriSuffix = "/full/full/full/native"
imageInfoSuffix = "/info.json"
manifestUriBase = ""
serviceBase = imageUriBase
profileLevel = "http://library.stanford.edu/iiif/image-api/1.1/conformance.html#level1"
attribution = "Provided by Harvard University"

HOLLIS_API_URL = "http://webservices.lib.harvard.edu/rest/MODS/hollis/"
HOLLIS_PUBLIC_URL = "http://hollisclassic.harvard.edu/F?func=find-c&CCL_TERM=sys="
 ## Add ISO639-2B language codes here where books are printed right-to-left (not just the language is read that way)
right_to_left_langs = set(['ara','heb'])

def process_page(sd, rangeKey, new_ranges):
	# first check if PAGE has label, otherwise get parents LABEL/ORDER				
	if 'LABEL' in sd.attrib:
		label = sd.get('LABEL')
	else:
		label = rangeKey
	for fid in sd.xpath('./mets:fptr/@FILEID', namespaces=ALLNS):
		if fid in imageHash.keys():
			info = {}
			info['label'] = label
			info['image'] = imageHash[fid]
			if info not in canvasInfo:
				canvasInfo.append(info)
			range = {}
			range[label] = imageHash[fid]
			new_ranges.append(range)

def process_struct_map(div, ranges):
	if 'LABEL' in div.attrib:
		rangeKey = div.get('LABEL')
	else:
		rangeKey = div.get('ORDER')

	# when the top level divs are PAGEs
	if 'TYPE' in div.attrib and div.get("TYPE") == 'PAGE':
		new_ranges = []
		process_page(div, rangeKey, new_ranges)
		if len(new_ranges) == 1:
			range_dict = new_ranges[0]			
			new_ranges = range_dict.get(range_dict.keys()[0])
		ranges.append({rangeKey : new_ranges})

	subdivs = div.xpath('./mets:div', namespaces = ALLNS)	
	if len(subdivs) > 0:
		new_ranges = []
		for sd in subdivs:
			# leaf node, get canvas info
			if 'TYPE' in sd.attrib and sd.get("TYPE") == 'PAGE':
				process_page(sd, rangeKey, new_ranges)
			else:
				new_ranges.extend(process_struct_map(sd, []))
		# this is for the books where every single page is labeled (like Book of Hours)
		# most books do not do this
		if len(new_ranges) == 1:
			range_dict = new_ranges[0]			
			new_ranges = range_dict.get(range_dict.keys()[0])
		ranges.append({rangeKey : new_ranges})
	return ranges
	
def get_leaf_canvases(ranges, leaf_canvases):
	for range in ranges:
		if type(range) is dict:
			value = range.get(range.keys()[0])
		else:
			value = range
		#if type(value) is list:
		if any(isinstance(x, dict) for x in value):
			get_leaf_canvases(value, leaf_canvases)
		else:
			leaf_canvases.append(value)

def create_range_json(ranges, manifest_uri, range_id, within, label):
	# this is either a nested list of dicts or one or more image ids in the METS
	if any(isinstance(x, dict) for x in ranges):
		leaf_canvases = []
		get_leaf_canvases(ranges, leaf_canvases)
		canvases = []
		for lc in leaf_canvases:
			canvases.append(manifest_uri + "/canvas/canvas-%s.json" % lc)
	else:
		canvases = [manifest_uri + "/canvas/canvas-%s.json" % ranges]

	rangejson =  {"@id": range_id,
		      "@type": "sc:Range",
		      "label": label,
		      "canvases": canvases
		      }
	# top level "within" equals the manifest_uri, so this range is a top level
	if within != manifest_uri:
		rangejson["within"] = within
	rangesJsonList.append(rangejson)

def create_ranges(ranges, previous_id, manifest_uri):
	if not any(isinstance(x, dict) for x in ranges):
		return

	counter = 0
	for ri in ranges:
		counter = counter + 1
		label = ri.keys()[0]
		if previous_id == manifest_uri:
			# these are for the top level divs
			range_id = manifest_uri + "/range/range-%s.json" % counter
		else:
			# otherwise, append the counter to the parent's id
			range_id = previous_id[0:previous_id.rfind('.json')] + "-%s.json" % counter
		new_ranges = ri.get(label)
		create_range_json(new_ranges, manifest_uri, range_id, previous_id, label)
		create_ranges(new_ranges, range_id, manifest_uri)
	
def main(data, document_id, source, host):
	# clear global variables
	global imageHash 
	imageHash = {}
	global canvasInfo 
	canvasInfo = []
	global rangesJsonList 
	rangesJsonList = []
	global manifestUriBase
	manifestUriBase = "https://%s/manifests/" % host

	dom = etree.XML(data)
	# Check if this is a DRS2 object since some things, like hollis ID are in a different location
	isDrs1 = True; 
	drs_check = dom.xpath('/mets:mets//premis:agentName/text()', namespaces=ALLNS)
	if len(drs_check) > 0 and 'DRS2' in '\t'.join(drs_check):
		isDrs1 = False

	manifestLabel = dom.xpath('/mets:mets/@LABEL', namespaces=ALLNS)[0]
	manifestType = dom.xpath('/mets:mets/@TYPE', namespaces=ALLNS)[0]

	if manifestType in ["PAGEDOBJECT", "PDS DOCUMENT"]:
		viewingHint = "paged"
	else:
		# XXX Put in other mappings here
		viewingHint = "individuals"

	## get language(s) from HOLLIS record, if there is one, (because METS doesn't have it) to determine viewing direction
	## TODO: top to bottom and bottom to top viewing directions
	## TODO: add Finding Aid links
	viewingDirection = 'left-to-right' # default
	seeAlso = ""
	if isDrs1:
		hollisCheck = dom.xpath('/mets:mets/mets:dmdSec/mets:mdWrap/mets:xmlData/mods:mods/mods:identifier[@type="hollis"]/text()', namespaces=ALLNS)
	else:
		hollisCheck = dom.xpath('/mets:mets/mets:amdSec//hulDrsAdmin:hulDrsAdmin/hulDrsAdmin:drsObject/hulDrsAdmin:harvardMetadataLinks/hulDrsAdmin:metadataIdentifier[../hulDrsAdmin:metadataType/text()="Aleph"]/text()', namespaces=ALLNS)
	if len(hollisCheck) > 0:
		hollisID = hollisCheck[0].strip()
		seeAlso = HOLLIS_PUBLIC_URL+hollisID
		response = urllib2.urlopen(HOLLIS_API_URL+hollisID).read()
		mods_dom = etree.XML(response)
		hollis_langs = set(mods_dom.xpath('/mods:mods/mods:language/mods:languageTerm/text()', namespaces=ALLNS))
		citeAs = mods_dom.xpath('/mods:mods/mods:note[@type="preferred citation"]/text()', namespaces=ALLNS)
		titleInfo = mods_dom.xpath('/mods:mods/mods:titleInfo/mods:title/text()', namespaces=ALLNS)[0]
		if len(citeAs) > 0:
			manifestLabel = citeAs[0] + " " + titleInfo
		# intersect both sets and determine if there are common elements
		if len(hollis_langs & right_to_left_langs) > 0:
			viewingDirection = 'right-to-left'

	manifest_uri = manifestUriBase + "%s:%s" % (source, document_id)

	images = dom.xpath('/mets:mets/mets:fileSec/mets:fileGrp/mets:file[@MIMETYPE="image/jp2"]', namespaces=ALLNS)
	struct = dom.xpath('/mets:mets/mets:structMap/mets:div[@TYPE="CITATION"]/mets:div', namespaces=ALLNS)

	# Check if the object has a stitched version(s) already made.  Use only those
	for st in struct:
		stitchCheck = st.xpath('./@LABEL[contains(., "stitched")]', namespaces=ALLNS)
		if stitchCheck:
			struct = st
			break

	for img in images:
		imageHash[img.xpath('./@ID', namespaces=ALLNS)[0]] = img.xpath('./mets:FLocat/@xlink:href', namespaces = ALLNS)[0]

	rangeList = []
	rangeInfo = []
	for st in struct:
		ranges = process_struct_map(st, [])
		rangeList.extend(ranges)
	if len(rangeList) > 1:
		rangeInfo = [{"Table of Contents" : rangeList}]

	mfjson = {
		"@context":"http://www.shared-canvas.org/ns/context.json",
		"@id": manifest_uri,
		"@type":"sc:Manifest",
		"label":manifestLabel,
		"attribution":attribution,
		"sequences": [
			{
				"@id": manifest_uri + "/sequence/normal.json",
				"@type": "sc:Sequence",
				"viewingHint":viewingHint,
				"viewingDirection":viewingDirection,
			}
		],
		"structures": []
	}

	if (seeAlso != ""):
		mfjson["seeAlso"] = seeAlso

	canvases = []
	for cvs in canvasInfo:
		response = urllib2.urlopen(imageUriBase + cvs['image'] + imageInfoSuffix)
		infojson = json.load(response)
		cvsjson = {
			"@id": manifest_uri + "/canvas/canvas-%s.json" % cvs['image'],
			"@type": "sc:Canvas",
			"label": cvs['label'],
			"height": infojson['height'],
			"width": infojson['width'],
			"images": [
				{
					"@id":manifest_uri+"/annotation/anno-%s.json" % cvs['image'],
					"@type": "oa:Annotation",
					"motivation": "sc:painting",
					"resource": {
						"@id": imageUriBase + cvs['image'] + imageUriSuffix,
						"@type": "dcterms:Image",
						"format":"image/jpeg",
						"height": infojson['height'],
						"width": infojson['width'],
						"service": { 
						  "@id": imageUriBase + cvs['image'],
						  "profile": profileLevel
						},
					},
					"on": manifest_uri + "/canvas/canvas-%s.json" % cvs['image']
				}
			]
		}
		canvases.append(cvsjson)

	# build table of contents using Range and Structures
	create_ranges(rangeInfo, manifest_uri, manifest_uri)

	mfjson['sequences'][0]['canvases'] = canvases
	mfjson['structures'] = rangesJsonList

	output = json.dumps(mfjson, indent=4, sort_keys=True)
	return output

if __name__ == "__main__":
	if (len(sys.argv) < 5):
		sys.stderr.write('not enough args\n')
		sys.stderr.write('usage: mets.py [input] [manifest_identifier] [data_source] [host]\n')
		sys.exit(0)

	inputfile = sys.argv[1]
	document_id = sys.argv[2]
	source = sys.argv[3]
	outputfile = source + '-' + document_id +  ".json"
	host = sys.argv[4]

	fh = file(inputfile)
	data = fh.read()
	fh.close()

	output = main(data, document_id, source, host)
	fh = file(outputfile, 'w')
	fh.write(output)
	fh.close()
