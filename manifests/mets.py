#!/usr/bin/python

from lxml import etree
import json, sys

metsNS = 'http://www.loc.gov/METS/'
modsNS = 'http://www.loc.gov/mods/v3'
xlinkNS = 'http://www.w3.org/1999/xlink'

ALLNS = {'mets':metsNS, 'mods':modsNS, 'xlink':xlinkNS}
imageHash = {}

def process_struct_map(st, canvasInfo):
	info = {}
	info['label'] = st.xpath('./@LABEL')[0]
#	sys.stderr.write(info['label'] + '\n')
#	print st.xpath('.//mets:fptr[2]/@FILEID', namespaces=ALLNS)
#	print etree.tostring(st)
#	if ( st.xpath('./mets:div/mets:fptr[2]/@FILEID', namespaces=ALLNS) ):
#		fid = st.xpath('./mets:div/mets:fptr[2]/@FILEID', namespaces=ALLNS)[0]
	# there can be a varied number of mets:div before the fptr
	if ( st.xpath('.//mets:fptr[2]/@FILEID', namespaces=ALLNS) ):
		fid = st.xpath('.//mets:fptr[2]/@FILEID', namespaces=ALLNS)[0]
	else:
		fid = st.xpath('./mets:fptr/@FILEID', namespaces=ALLNS)[0]
		# might need to change xpath

#	sys.stderr.write(fid + '\n')
#	print fid, info
	info['image'] = imageHash[fid]
	canvasInfo.append(info)

def main(data, outputIdentifier):
	imageWidth = 2400
	imageHeight = 2400

	dom = etree.XML(data)

	#imageUriBase = "http://idstest.lib.harvard.edu:9001/ids/iiif/"
	imageUriBase = "http://ids.lib.harvard.edu/ids/iiif/"
	imageUriSuffix = "/full/full/full/native"
	manifestUriBase = "http://ids.lib.harvard.edu/iiif/metadata/"
	#manifestUriBase = "http://idstest.lib.harvard.edu:9001/ids/manifest/"
	serviceBase = imageUriBase
	profileLevel = "http://library.stanford.edu/iiif/image-api/1.1/conformance.html#level1"


	manifestLabel = dom.xpath('/mets:mets/@LABEL', namespaces=ALLNS)[0]
	manifestType = dom.xpath('/mets:mets/@TYPE', namespaces=ALLNS)[0]

	if manifestType == "PAGEDOBJECT":
		viewingHint = "paged"
	else:
		# XXX Put in other mappings here
		viewingHint = "individuals"

	identifier = dom.xpath('/mets:mets/mets:dmdSec/mets:mdWrap[@MDTYPE="MODS"]/mets:xmlData/mods:mods/mods:identifier/text()', namespaces=ALLNS)[0]
	identifierType = dom.xpath('/mets:mets/mets:dmdSec/mets:mdWrap[@MDTYPE="MODS"]/mets:xmlData/mods:mods/mods:identifier/@type', namespaces=ALLNS)[0]

	#manifestUriBase += "%s/%s/" % (identifierType, identifier)
	manifestUriBase += "%s/" % (outputIdentifier)

	images = dom.xpath('/mets:mets/mets:fileSec/mets:fileGrp/mets:file[@MIMETYPE="image/jp2"]', namespaces=ALLNS)
	struct = dom.xpath('/mets:mets/mets:structMap/mets:div[@TYPE="CITATION"]/mets:div', namespaces=ALLNS)

	for img in images:
		imageHash[img.xpath('./@ID', namespaces=ALLNS)[0]] = img.xpath('./mets:FLocat/@xlink:href', namespaces = ALLNS)[0]

	#print imageHash
	canvasInfo = []
	for st in struct:
	#	print(st.xpath('./@LABEL')[0])
		subdivs = st.xpath('./mets:div[@LABEL]', namespaces = ALLNS)
	#	print len(subdivs)

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
		"@id": manifestUriBase + "manifest.json",
		"@type":"sc:Manifest",
		"label":manifestLabel,
		"attribution":"Provided by the Houghton Library, Harvard University",
		"viewingHint":viewingHint,
		"sequences": [
			{
				"@id": manifestUriBase + "sequence/normal.json",
				"@type": "sc:Sequence",
			}
		]
	}

	canvases = []

	for cvs in canvasInfo:
		cvsjson = {
			"@id": manifestUriBase + "canvas/canvas-%s.json" % cvs['image'],
			"@type": "sc:Canvas",
			"label": cvs['label'],
			#"height": imageHeight,
			#"width": imageWidth,
			"resources": [
				{
					"@id":manifestUriBase+"annotation/anno-%s.json" % cvs['image'],
					"@type": "oa:Annotation",
					"motivation": "sc:painting",
					"resource": {
						"@id": imageUriBase + cvs['image'] + imageUriSuffix,
						"@type": "dcterms:Image",
						"format":"image/jpeg",
						#"height": imageHeight,
						"service": { 
						  "@id": imageUriBase + cvs['image'],
						  "profile": profileLevel
						},
						#"width": imageWidth					
					},
					"on": manifestUriBase + "canvas/canvas-%s.json" % cvs['image']
				}
			]
		}
		canvases.append(cvsjson)

	rangeInfo = []
	# build table of contents using Range and Structures
	for st in struct:
		label = st.xpath('./@LABEL')[0]
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
	if (len(sys.argv) < 3):
		sys.stderr.write('not enough args\n')
		sys.stderr.write('usage: mets.py input manifest_identifier\n')
		sys.exit(0)

	inputfile = sys.argv[1]
	outputIdentifier = sys.argv[2]
	outputfile = outputIdentifier +  ".json"
	isDrs1 = True; # add functionality for drs2

	fh = file(inputfile)
	data = fh.read()
	fh.close()

	output = main(data, outputIdentifier)
	fh = file(outputfile, 'w')
	fh.write(output)
	fh.close()
