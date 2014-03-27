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

## TODO: Other image servers?
imageUriBase = "http://ids.lib.harvard.edu/ids/iiif/"
imageUriSuffix = "/full/full/full/native"
manifestUriBase = "http://oculus-dev.lib.harvard.edu/manifests/"
serviceBase = imageUriBase
profileLevel = "http://library.stanford.edu/iiif/image-api/1.1/conformance.html#level1"
attribution = "Provided by Harvard University"

HOLLIS_URL = "http://webservices.lib.harvard.edu/rest/MODS/hollis/"
 ## Add ISO639-2B language codes here where books are printed right-to-left (not just the language is read that way)
right_to_left_langs = set(['ara','heb'])

def process_struct_map(st, canvasInfo):
	if 'LABEL' in st.attrib:
		label = st.xpath('./@LABEL')[0]
	else:
		label = st.xpath('./@ORDER')[0]

	for fid in st.xpath('.//mets:fptr/@FILEID', namespaces=ALLNS):
		info = {}
		info['label'] = label
		if fid in imageHash.keys():
			info['image'] = imageHash[fid]
			canvasInfo.append(info)

def main(data, document_id, source):
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
	viewingDirection = 'left-to-right' # default
	if isDrs1:
		hollisCheck = dom.xpath('/mets:mets/mets:dmdSec/mets:mdWrap/mets:xmlData/mods:mods/mods:identifier[@type="hollis"]/text()', namespaces=ALLNS)
	else:
		hollisCheck = dom.xpath('/mets:mets/mets:amdSec//hulDrsAdmin:hulDrsAdmin/hulDrsAdmin:drsObject/hulDrsAdmin:harvardMetadataLinks/hulDrsAdmin:metadataIdentifier[../hulDrsAdmin:metadataType/text()="Aleph"]/text()', namespaces=ALLNS)
	if len(hollisCheck) > 0:
		hollisID = hollisCheck[0].strip()
		response = urllib2.urlopen(HOLLIS_URL+hollisID).read()
		mods_dom = etree.XML(response)
		hollis_langs = set(mods_dom.xpath('/mods:mods/mods:language/mods:languageTerm/text()', namespaces=ALLNS))
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
			#print(etree.tostring(st, pretty_print=True))
			struct = st
			break

	for img in images:
		imageHash[img.xpath('./@ID', namespaces=ALLNS)[0]] = img.xpath('./mets:FLocat/@xlink:href', namespaces = ALLNS)[0]

	#print imageHash
	canvasInfo = []
	for st in struct:
		subdivs = st.xpath('./mets:div[@LABEL]', namespaces = ALLNS)

		# need to be able to handle any number of nesting
		if len(subdivs) > 0:
			# need to process subdivs because object has nesting
			# there should be a max of 3 levels, but will need more testing
			for sd in subdivs:
				subdivs2 = sd.xpath('./mets:div[@LABEL]', namespaces = ALLNS)
				if len(subdivs2) > 0:
					for sd2 in subdivs2:
						process_struct_map(sd2, canvasInfo)
				else:
					process_struct_map(sd, canvasInfo)
		else:
			process_struct_map(st, canvasInfo)	

	mfjson = {
		"@context":"http://www.shared-canvas.org/ns/context.json",
		"@id": manifest_uri,
		"@type":"sc:Manifest",
		"label":manifestLabel,
		"attribution":attribution,
		"viewingHint":viewingHint,
		"viewingDirection":viewingDirection,
		"sequences": [
			{
				"@id": manifest_uri + "/sequence/normal.json",
				"@type": "sc:Sequence",
			}
		]
	}

	canvases = []

	for cvs in canvasInfo:
		cvsjson = {
			"@id": manifest_uri + "/canvas/canvas-%s.json" % cvs['image'],
			"@type": "sc:Canvas",
			"label": cvs['label'],
			"images": [
				{
					"@id":manifest_uri+"/annotation/anno-%s.json" % cvs['image'],
					"@type": "oa:Annotation",
					"motivation": "sc:painting",
					"resource": {
						"@id": imageUriBase + cvs['image'] + imageUriSuffix,
						"@type": "dcterms:Image",
						"format":"image/jpeg",
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

	## TODO
	rangeInfo = []
	# build table of contents using Range and Structures
	for st in struct:
		if 'LABEL' in st.attrib:
			label = st.xpath('./@LABEL')[0]
		else:
			label = st.xpath('./@ORDER')[0]

		#print "Label: %s" % label
		subdivs = st.xpath('./mets:div[@LABEL]', namespaces = ALLNS)
		while len(subdivs) > 0:
			for sd in subdivs:
				label = sd.xpath('./@LABEL')[0]
				#print "Label: %s" % label
				parent = sd.xpath('../mets:div[@LABEL]', namespaces = ALLNS)
				if len(parent) == 1:
					within = parent.xpath('./@LABEL')[0]
					#print "%s within %s" % (label, within)
				subdivs = sd.xpath('./mets:div[@LABEL]', namespaces = ALLNS)

	mfjson['sequences'][0]['canvases'] = canvases
	#mfjson['structures'][0] = ranges

	output = json.dumps(mfjson, indent=4, sort_keys=True)
	return output

if __name__ == "__main__":
	if (len(sys.argv) < 4):
		sys.stderr.write('not enough args\n')
		sys.stderr.write('usage: mets.py input manifest_identifier data_source\n')
		sys.exit(0)

	inputfile = sys.argv[1]
	document_id = sys.argv[2]
	source = sys.argv[3]
	outputfile = source + '-' + document_id +  ".json"

	fh = file(inputfile)
	data = fh.read()
	fh.close()

	output = main(data, document_id, source)
	fh = file(outputfile, 'w')
	fh.write(output)
	fh.close()
