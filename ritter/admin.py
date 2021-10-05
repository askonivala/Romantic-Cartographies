# (C) 2021 Dr. Asko Nivala (aeniva at utu dot fi)
# University of Turku
# Published with MIT License: https://github.com/askonivala/Romantic-Cartographies

from ritter import app
from ritter.NLP import nel_scan

from flask_admin import Admin
from flask_admin.contrib.mongoengine import ModelView
from mongoengine import *
from mongoengine import signals
import json
import markdown

import threading
import sparql
import time
import geojson

# set optional bootswatch theme
app.config['FLASK_ADMIN_SWATCH'] = 'cerulean'
admin = Admin(app, name='Ritter', template_mode='bootstrap3')

# PLEASE NOTE:
# This is an example using local Mongo DB for development purposes.
# You need to set up authentification for Mongo DB for production.
connect('ritter')

# Entity mentioned in a text
class Entity(EmbeddedDocument):
	external_URI = URLField()
	support = IntField()
	surfaceForm = StringField()
	offset = IntField()
	similarityScore = IntField()
	percentageOfSecondRank = IntField()
	types = DictField()
	internal_URI = StringField()

	def __unicode__(self):
		return self.external_URI

# A paragrahp embedded in a chapter
class Paragraph(EmbeddedDocument):
	number = IntField()
	text = StringField()
	confidence = FloatField()
	support = IntField()
	types = DictField()
	sparql = StringField()
	policy = StringField()
	entities = ListField(EmbeddedDocumentField('Entity'))
	# sentiment = IntField()
	error = StringField()

	def __unicode__(self):
		return self.text

# A chapter embedded in a text
class Chapter(EmbeddedDocument):
	number = IntField()
	title = StringField()
	paragraphs = ListField(EmbeddedDocumentField('Paragraph'))

	def __unicode__(self):
		return self.title

# An author of a text
class Author(Document):
	entity_id = StringField(required=True)
	# URI = 'http://dbpedia.org/resource/Novalis'
	URI = URLField(required=True)
	first_name = StringField()
	last_name = StringField()
	alias = StringField()

	def __unicode__(self):
		return self.entity_id

def parse_dbpedia_types(type_string):
	dbpedia_dict = {}
	if type_string == '':
		pass
	else:
		tags = type_string.split(',')
		for tag in tags:
			dict_parts = tag.split(':')
			if dict_parts[0] in dbpedia_dict:
				dbpedia_dict[dict_parts[0]].append(dict_parts[1])
			else:
				dbpedia_dict[dict_parts[0]] = []
				dbpedia_dict[dict_parts[0]].append(dict_parts[1])
	return dbpedia_dict

def parse_entities(entities, paragraph_no):
	# returns a dict for mongoengine, entities objects embedded
	scan_results = json.loads(entities.content)
	paragraph_data = {}

	paragraph_data['number'] = int(paragraph_no)
	paragraph_data['text'] = scan_results['@text']
	paragraph_data['confidence'] = float(scan_results['@confidence'])
	paragraph_data['support'] = int(scan_results['@support'])
	paragraph_data['types'] = parse_dbpedia_types(scan_results['@types'])
	paragraph_data['sparql'] = scan_results['@sparql']
	paragraph_data['policy'] = scan_results['@policy']

	# make a list for mongonegine objects
	paragraph_data['entities'] = []

	# parse entities
	if 'Resources' in scan_results:
		for entity in scan_results['Resources']:
			entity_dict = {}
			# TODO: check that link exists
			entity_dict['external_URI'] = entity['@URI']
			entity_dict['support'] = entity['@support']
			entity_dict['surfaceForm'] = entity['@surfaceForm']
			print('found:', entity['@surfaceForm'])
			entity_dict['offset'] = int(entity['@offset'])
			entity_dict['similarityScore'] = float(entity['@similarityScore'])
			entity_dict['percentageOfSecondRank'] = float(entity['@percentageOfSecondRank'])
			entity_dict['types'] = parse_dbpedia_types(entity['@types'])

			# classify entity
			entity_name = entity_dict['surfaceForm'].replace(' ', '_')
			nel_entity = Entity(**entity_dict)
			paragraph_data['entities'].append(nel_entity)
	return paragraph_data

def check_if_done(URI):

	results = Place.objects(URI=URI)

	if len(results) == 1:
		return True
	elif len(results) == 0:
		de_results = Place.objects(de_URI=URI)
		if len(de_results) == 1:
			return True
		if len(de_results) == 0:
			return False
		elif len(de_results) > 1:
			return True
			# print('Error: found duplicate from DB with Place URI', results)
			# sys.exit(0)
	elif len(results) > 1:
		return True
		# print('Error: found duplicate from DB with Place URI', results)
		# sys.exit(0)

def find_english_coords(uri):
	# query_place_name = place_name.replace(' ', '_')
	# query = 'SELECT ?x {dbr:' + query_place_name + ' georss:point ?x.}'
	query = 'SELECT ?x {<' + uri + '> georss:point ?x.}'
	result = sparql.query('http://dbpedia.org/sparql', query)
	time.sleep(3)
	for row in result:
		raw_coords = sparql.unpack_row(row)

	if 'raw_coords' in locals():
		coords = raw_coords[0].split(' ')
		geometry = geojson.Point((float(coords[1]), float(coords[0])))
	else:
		geometry = ''

	return geometry

def save_place(URI, place_name, en_place_name, point_geometry, polygon_geometry, de_URI, type):
	# new_place = admin.Place(entity_id=internal_URI, title=workdata['title'], long_title=workdata['long_title'], authors=authors, pub_year=workdata['pub_year'])
	underscored_place_name = en_place_name.replace(' ','_')
	internal_URI = '/place/' + underscored_place_name

	en_place_name = en_place_name.replace('_',' ')

	# to differentiate between "Rome" and "Ancient Rome" when surfaceForm is "Rome"
	entity = URI.lstrip('http://dbpedia.org/resource/')
	entity = URI.lstrip('http://de.dbpedia.org/resource/')
	entity = entity.replace('_',' ')

	if point_geometry != '':
		# lat, long = point_geometry.lstrip('POINT(').split(' ')
		# lat = float(lat)
		# long = long.rstrip(')')
		# long = float(long)
		# parsed_geometry = geojson.Point((lat, long))
		if de_URI:
			new_place = Place(entity_id=internal_URI, URI=URI, name=place_name, en_name=en_place_name, entity=entity, shape=point_geometry, de_URI=de_URI, type=type)
		else:
			new_place = Place(entity_id=internal_URI, URI=URI, name=place_name, en_name=en_place_name, entity=entity, shape=point_geometry, type=type)
		new_place.save()
		print('SAVED: ', place_name)
		return
	elif polygon_geometry != '':
		parsed_geometry = geojson.MultiPolygon(polygon_geometry)
		if de_URI:
			new_place = Place(entity_id=internal_URI, URI=URI, name=place_name, en_name=en_place_name, entity=entity, polygon_shape=parsed_geometry, de_URI=de_URI, type=type)
		else:
			new_place = Place(entity_id=internal_URI, URI=URI, name=place_name, en_name=en_place_name, entity=entity, polygon_shape=parsed_geometry, type=type)
		new_place.save()
		print('SAVED: ', place_name)
		return
	else:
		if de_URI:
			new_place = Place(entity_id=internal_URI, URI=URI, name=place_name, en_name=en_place_name, entity=entity, de_URI=de_URI, type=type)
		else:
			new_place = Place(entity_id=internal_URI, URI=URI, name=place_name, en_name=en_place_name, entity=entity, type=type)
		new_place.save()
		print('SAVED: ', place_name)
		return

def solve_place(URI, place_name, type):
	if check_if_done(URI) == False:
		geometry = find_english_coords(URI)
		if geometry != '':
			save_place(URI, place_name, en_place_name=place_name, point_geometry=geometry, polygon_geometry='', de_URI='', type=type)
		else:
			print('Cannot find geometry for: ', place_name)

def geolocate_nel_document(document):
	print('Starting geolocating:', document.internal_URI)
	for chapter in document.chapters:
		for paragraph in chapter.paragraphs:
			if "entities" in paragraph:
				for entity in paragraph.entities:
					if "DBpedia" in entity.types:
						if "Place" in entity.types["DBpedia"] or "Location" in entity.types["DBpedia"] or "Settlement" in entity.types["DBpedia"] or "PopulatedPlace" in entity.types["DBpedia"]:
							# blacklist clearly wrong places
							if "LunarCrater" in entity.types["DBpedia"]:
								pass
							else:
								# print('Searching for ', entity.surfaceForm)
								solve_place(URI=entity.external_URI, place_name=entity.surfaceForm, type=entity.types["DBpedia"])

def nel_background_analysis(document):

	def nel_analysis(document):
		# TODO: need to implement division into chapters
		raw_paragraphs = nel_scan.preprocess_paragraphs(document.fulltext)
		nel_paragraphs = []

		paragraph_number = 0
		for paragraph in raw_paragraphs:
			clean_paragraph = paragraph.replace('\n',' ')
			if len(clean_paragraph) <= 2:
				pass
			else:
				entities = nel_scan.scan_text(clean_paragraph, type='json', filter_types=True)
				paragraph_number = paragraph_number + 1
				paragraph_data = parse_entities(entities, paragraph_number)
				nel_paragraph = Paragraph(**paragraph_data)
				nel_paragraphs.append(nel_paragraph)

		chapter_data = {"number":0, "title":'Chapter 1'}
		chapter_data['paragraphs'] = nel_paragraphs
		nel_chapter = Chapter(**chapter_data)
		nel_document = nel(internal_URI=document)
		nel_document.chapters = [nel_chapter]
		nel_document.save()
		geolocate_nel_document(nel_document)
		# TODO: update mentions to all documents!

	thread = threading.Thread(target=nel_analysis, kwargs={'document': document})
	thread.start()
	return 'started'

class Text(Document):
	entity_id = StringField(required=True)
	# URI = 'http://dbpedia.org/resource/Ivanhoe'
	URI = URLField()
	title = StringField(required=True)
	# lang = 'en', 'de' etc.
	lang = StringField(required=True)
	long_title = StringField()
	authors = ListField(ReferenceField(Author))
	pub_year = DateTimeField(required=True)
	# TODO: add support for scanning URL-links from Gutenberg and other sites
	fulltext = StringField()

	def __unicode__(self):
		return self.entity_id

	# Run NEL analysis after a text is saved to database
	@classmethod
	def post_save(cls, sender, document, **kwargs):
		print("Running NEL analysis: %s" % document.entity_id)
		if 'created' in kwargs:
			if kwargs['created']:
				nel_background_analysis(document)
			else:
				print("Updated Text, not NEL-scanning.")

signals.post_save.connect(Text.post_save, sender=Text)

class nel(Document):
	internal_URI = ReferenceField(Text)
	chapters = ListField(EmbeddedDocumentField('Chapter'))
	#date_modified = DateTimeField()

	def __unicode__(self):
		return self.internal_URI

class Place(Document):
	entity_id = StringField()
	URI = URLField()
	de_URI = URLField()
	name = StringField()
	en_name = StringField()
	entity = StringField()
	type = ListField(StringField())
	# alternate_names = ListField(StringField())

	# Flask Admin does not support geographic data; at the moment you need to
	# edit this from the Mongo client.
	shape = PointField()
	polygon_shape = MultiPolygonField()

	def __unicode__(self):
		return self.name

class Character(Document):
	# internal API-uri, e.g. /character/Lord_Ruthven
	entity_id = StringField()
	# external URI for DBpedia
	URI = URLField()
	texts = ListField(ReferenceField(Text))

	name = StringField()

	def __unicode__(self):
		return self.entity_id

class Waypoint(EmbeddedDocument):
	# This can be a travel route between two places or a rhetorical comparison like
	# "Dresden is the new Athens", which connects two places.

	# Where the travel or juxtaposition begins and ends
	source = ReferenceField('Place', required=True)
	target = ReferenceField('Place', required=True)

	# 'travel' or 'comparison' etc.
	type = ListField(StringField(), required=True)

	# You can describe the way as a MarkDown-encoded commentary, which is shown
	# in the popup window.
	md_interpretation = StringField()

	# You can quote this scene from the text (if you want).
	quote = StringField()

	# Who travels or makes juxtaposition?
	character = ListField(ReferenceField(Character))

	# Where it happens in the text?
	volume = IntField()
	chapter = IntField()
	paragraph = IntField()

	# intertexts
	intertexts = ListField(ReferenceField(Text))

	def __unicode__(self):
		return self.entity_id

class Scholar(Document):
	entity_id = StringField()
	URI = URLField()
	first_name = StringField()
	last_name = StringField()
	alias = StringField()

	def __unicode__(self):
		return self.entity_id

class Way(Document):
	# Can be a travel route, but also a juxtaposition between two places.

	# e.g. /way/Aubrey_in_Vampyre
	internal_uri = StringField(max_length=200, required=True)

	# e.g., "Aubrey's travel in The Vampyre"
	name = StringField(max_length=200, required=True)

	# e.g., /scholar/Asko_Nivala BUT
	scholar = ReferenceField(Scholar)
	# Source as BIBTEX.
	bib_reference = StringField()

	# Scholarly interpretation as MarkDown.
	md_interpretation = StringField()

	# e.g., the text object of "The Vampyre"
	title = ReferenceField(Text)

	# type
	tags = ListField(StringField())

	# Each "Waypoint" is an EDGE that has TWO nodes.
	waypoints = ListField(EmbeddedDocumentField('Waypoint'))

	def __unicode__(self):
		return self.name

# Add views
admin.add_view(ModelView(Author))
admin.add_view(ModelView(Text))
admin.add_view(ModelView(nel))
admin.add_view(ModelView(Place))
admin.add_view(ModelView(Character))
admin.add_view(ModelView(Way))
admin.add_view(ModelView(Scholar))
