# (C) 2021 Dr. Asko Nivala (aeniva at utu dot fi)
# University of Turku
# Published with MIT License: https://github.com/askonivala/Romantic-Cartographies

import requests
import sys
import json
import datetime

# for splitting too long paragraphs
import math
from string import ascii_lowercase

# An API Error Exception
class APIError(Exception):
	def __init__(self, status, content):
		self.status = status
		self.content = content

	def __str__(self):
		return "APIError: status={}, error={}".format(self.status, self.content)

# Base URL for Spotlight API
# TODO: read from a configuration file.
#base_url = "http://127.0.0.1:2222/rest/annotate"

def scan_text(text, confidence=0.70, filter_types=True, type='json'):

	base_url = "https://api.dbpedia-spotlight.org/en/annotate"

	if filter_types == True:
		types = "Schema:Place,DBpedia:Settlement,DBpedia:PopulatedPlace,DBpedia:Place,DBpedia:Location,Schema:Country,DBpedia:Country,DBpedia:AdministrativeRegion,Schema:AdministrativeArea"
		params = {"text": text, "confidence": confidence, "types": types}
	elif filter_types == False:
		params = {"text": text, "confidence": confidence}

	# Response content type
	if type == 'html':
		headers = {'accept': 'text/html'}
	if type == 'json':
		headers = {'accept': 'application/json'}

	# GET Request
	res = requests.get(base_url, params=params, headers=headers)

	if res.status_code != 200:
		# Something went wrong
		print(res.content)
		raise APIError(res.status_code, res.content)

	return(res)

def without_keys(d, keys):
	 return {x: d[x] for x in d if x not in keys}

def chunkIt(seq, num):
    avg = len(seq) / float(num)
    out = []
    last = 0.0

    while last < len(seq):
        out.append(seq[int(last):int(last + avg)])
        last += avg

    return out

def split_paragraph(text):
	print('SPLITTING')
	text_lenght = len(text)
	min_parts = text_lenght / 7000
	parts_average = math.ceil(min_parts)
	# min_parts = round(min_parts)
	tokens = text.split(' ')
	split_tokens = chunkIt(tokens, parts_average)

	split_paragraphs = []
	for paragraph_tokens in split_tokens:
		paragraph_text = ' '.join(paragraph_tokens)
		split_paragraphs.append(paragraph_text)

	return split_paragraphs

def measure_paragraph_average(chapter):

	# test paragraph lenght
	test_chapter_text = chapter.replace('\r\n','\n\n')
	test_paragraphs = test_chapter_text.split('\n\n')

	paragraph_lenghts = []
	for paragraph in test_paragraphs:
		paragraph_lenghts.append(len(paragraph))
	paragraph_average = sum(paragraph_lenghts) / len(test_paragraphs)

	if paragraph_average < 300:
		paragraph_separator = '\n\n\n\n'
	else:
		paragraph_separator = '\n\n'

	return paragraph_separator

def preprocess_paragraphs(chapter):
	# optimize paragraph separator character based on average lenght
	paragraph_separator = measure_paragraph_average(chapter)

	# harmonize the separators
	chapter_text = chapter.replace('\r\n','\n\n')

	# split chapter to paragraphs
	paragraphs = chapter_text.split(paragraph_separator)

	# remove empty paragraphs
	while('' in paragraphs):
		paragraphs.remove('')
	while('\n' in paragraphs):
		paragraphs.remove('\n')

	return paragraphs

def nelscan_paragraph(paragraph_no, paragraph, scanned_paragraph_counter, lang):
	scan_results = []
	paragraph_data = {}
	# remove line changes
	clean_paragraph = paragraph.replace('\n',' ')

	# need check for API error

	try:
		if len(clean_paragraph) <= 2:
			scan_result = {}
			scan_result['scan_status'] = False
			scan_results.append(scan_result)

		elif len(clean_paragraph) < 7000:

			entities = scan_text(clean_paragraph, type='json', filter_types=False)
			paragraph_data = parse_entities(entities, scanned_paragraph_counter)

			scan_result = {}
			scan_result['paragraph_data'] = paragraph_data
			scan_result['scan_status'] = True
			scan_result['scanned_paragraph_counter'] = scanned_paragraph_counter + 1
			scan_results.append(scan_result)

		elif len(clean_paragraph) >= 7000:
			split_paragraphs = split_paragraph(clean_paragraph)

			for short_paragraph in split_paragraphs:
				print('      short paragraph lenght', len(short_paragraph))
				entities = scan_text(short_paragraph, type='json', filter_types=False)
				paragraph_data = parse_entities(entities, scanned_paragraph_counter)
				scanned_paragraph_counter = scanned_paragraph_counter + 1

				scan_result = {}
				scan_result['paragraph_data'] = paragraph_data
				scan_result['scan_status'] = True
				scan_result['scanned_paragraph_counter'] = scanned_paragraph_counter
				scan_results.append(scan_result)

	except APIError:
		print('API Error:')
		print(clean_paragraph)

		paragraph_data = {}
		paragraph_data['number'] = int(scanned_paragraph_counter)
		paragraph_data['text'] = clean_paragraph
		paragraph_data['error'] = 'DBpedia API error'

		scan_result = {}
		scan_result['paragraph_data'] = paragraph_data
		scan_result['scan_status'] = True
		scan_result['scanned_paragraph_counter'] = scanned_paragraph_counter + 1
		scan_results.append(scan_result)

	return scan_results

def collect_chapter(chapter, lang):

	#collect chapter metadata as dict
	chapter_data = {'number': chapter[0]}
	chapter_no = int(chapter[0]) + 1
	chapter_title = 'Chapter ' + str(chapter_no)
	chapter_data['title'] = chapter_title

	# init list of mongonengine objects
	chapter_data['paragraphs'] = []

	# preprocess the paragraphs of chapter
	paragraphs = preprocess_paragraphs(chapter)

	scanned_paragraph_counter = 0
	# make paragraphs mongoengine objects
	for paragraph_no, paragraph in enumerate(paragraphs):
		scan_results = nelscan_paragraph(paragraph_no, paragraph, scanned_paragraph_counter, lang)
		# scan results is a list because there a splitted paragraphs
		for scan_result in scan_results:
			if scan_result['scan_status'] == True:
				scanned_paragraph_data = scan_result['paragraph_data']
				nel_paragraph = admin.Paragraph(**scanned_paragraph_data)
				chapter_data['paragraphs'].append(nel_paragraph)
				scanned_paragraph_counter = scan_result['scanned_paragraph_counter']
			else:
				continue

	# need to return a dict (chapter_data) for mongonengine object
	return chapter_data
