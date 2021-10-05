# (C) 2021 Dr. Asko Nivala (aeniva at utu dot fi)
# University of Turku
# Published with MIT License: https://github.com/askonivala/Romantic-Cartographies

from ritter import app
from ritter import admin

from flask import render_template, Response, jsonify, request, redirect, url_for
from flaskext.markdown import Markdown
#Markdown(app, extensions=['footnotes'])
Markdown(app)

import geojson
import json

import markdown
import pandas as pd

@app.route('/')
@app.route('/index')
def index():
	ways = admin.Way.objects()

	# make GeoJSON
	COLOR_NAMES = ["Red","Blue","Green","Yellow","Purple","Black","White","Fuchsia","Navy","Maroon","Silver","Olive","Aqua","Gray","Lime","Teal"]
	color_index = 0
	geofeature_list = []
	for way in ways:
		# TODO: change style for each way for legend
		for waypoint in way.waypoints:
			source_feature = geojson.Feature(
				geometry=geojson.Point((waypoint.source.shape['coordinates'][0],waypoint.source.shape['coordinates'][1])),
				properties={"name": waypoint.source.name}
			)
			geofeature_list.append(source_feature)
			target_feature = geojson.Feature(
				geometry=geojson.Point((waypoint.target.shape['coordinates'][0],waypoint.target.shape['coordinates'][1])),
				properties={"name": waypoint.target.name}
			)
			geofeature_list.append(target_feature)
			html_title = "<a href=" + way.internal_uri +"><i>" + way.title.title + "</i></a>"
			style = COLOR_NAMES[color_index]
			line_feature = geojson.Feature(
				geometry=geojson.LineString([(waypoint.source.shape['coordinates'][0],waypoint.source.shape['coordinates'][1]),(waypoint.target.shape['coordinates'][0],waypoint.target.shape['coordinates'][1])]),
				properties={"name": html_title, "style": style, "type": waypoint.type[0]}
			)
			geofeature_list.append(line_feature)
		color_index = color_index + 1
	routes_geojson_map = geojson.FeatureCollection(geofeature_list)
	return render_template('ways.html', ways=ways, routes_geojson_map=routes_geojson_map)

@app.route('/way/<way_name>')
def show_way(way_name):
	way_id = '/way/' + way_name
	way = admin.Way.objects.get(internal_uri=way_id)

	geofeature_list = []
	for waypoint in way.waypoints:
		source_feature = geojson.Feature(
			geometry=geojson.Point((waypoint.source.shape['coordinates'][0],waypoint.source.shape['coordinates'][1])),
			properties={"name": waypoint.source.name}
		)
		geofeature_list.append(source_feature)
		target_feature = geojson.Feature(
			geometry=geojson.Point((waypoint.target.shape['coordinates'][0],waypoint.target.shape['coordinates'][1])),
			properties={"name": waypoint.target.name}
		)
		geofeature_list.append(target_feature)
		html_desc = markdown.markdown(waypoint.md_interpretation)
		style = "Red"
		line_feature = geojson.Feature(
			geometry=geojson.LineString([(waypoint.source.shape['coordinates'][0],waypoint.source.shape['coordinates'][1]),(waypoint.target.shape['coordinates'][0],waypoint.target.shape['coordinates'][1])]),
			properties={"name": html_desc, "style": style, "type": waypoint.type[0]}
		)
		geofeature_list.append(line_feature)
	routes_geojson_map = geojson.FeatureCollection(geofeature_list)

	way_desc = markdown.markdown(way.md_interpretation, extensions=['footnotes'])

	return render_template('show_way.html', way=way, routes_geojson_map=routes_geojson_map, way_desc=way_desc)

@app.route('/authors')
def show_authors():
	authors = admin.Author.objects.only('entity_id','first_name','last_name')
	parsed_authors = []
	for author in authors:
		author_dict = {}
		author_dict['entity_id'] = author['entity_id']
		author_dict['first_name'] = author['first_name']
		author_dict['last_name'] = author['last_name']
		parsed_authors.append(author_dict)
	return render_template('authors.html', authors=parsed_authors)

@app.route('/author/<author_name>')
def show_author(author_name):
	author_id = '/author/' + author_name
	author_texts = []
	parsed_author_name = author_name.replace('_',' ')
	texts = admin.Text.objects()
	for text in texts:
		for author in text.authors:
			if author.entity_id == author_id:
				author_texts.append(text)
	parsed_texts = []
	for text in author_texts:
		text_dict = {}
		text_dict['title'] = text['title']
		text_dict['entity_id'] = text['entity_id']
		parsed_year = text['pub_year'].year
		text_dict['pub_year'] = parsed_year
		parsed_texts.append(text_dict)
	return render_template('author_nel.html', texts=parsed_texts, author_name=parsed_author_name)

@app.route('/nel')
def show_nel():
	texts = admin.Text.objects.only('entity_id','pub_year','title','authors')
	parsed_texts = []
	for text in texts:
		text_dict = {}
		text_dict['title'] = text['title']
		text_dict['entity_id'] = text['entity_id']
		parsed_year = text['pub_year'].year
		text_dict['pub_year'] = parsed_year
		list_of_authors = []
		for author in text.authors:
			author_fullname = author.last_name + ', ' + author.first_name
			list_of_authors.append(author_fullname)
			parsed_authors = '; '.join(list_of_authors)
		text_dict['authors'] = parsed_authors
		parsed_texts.append(text_dict)
	return render_template('nel.html', texts=parsed_texts)

def convert_to_markdown(text):
	# TODO: add support for changing the threshold!
	support_threshold = 1500
	markup_data = {}
	markup_data['chapters'] = {}
	other_entities = []
	blacklist = ['rock','Rock','Diana','exclaim','corn','Fiat','smack','Die Welt','Die Zeit','Das Erste','RICHMOND','soul']
	all_places = []
	for chapter in text.chapters:
		markup_data['chapters'][str(chapter.number)] = {}
		for paragraph in chapter.paragraphs:
			markup_data['chapters'][str(chapter.number)][str(paragraph.number)] = {}
			if "text" in paragraph:
				raw_text = paragraph['text']
				if "entities" in paragraph:
					if bool(paragraph["entities"]) == True:
						entities = paragraph["entities"]

						# separate places and other entities
						for entity in entities:
							all_entities_dict = {}
							if entity['support'] >= support_threshold and entity.surfaceForm not in blacklist:
								if "DBpedia" in entity.types:
									# is it a place?
									if "Place" in entity.types["DBpedia"] or "Location" in entity.types["DBpedia"] or "Settlement" in entity.types["DBpedia"] or "PopulatedPlace" in entity.types["DBpedia"]:
										all_entities_dict['URI'] = entity.external_URI
										all_entities_dict['name'] = entity.surfaceForm
										all_entities_dict['type'] = ', '.join(entity.types["DBpedia"])
										all_places.append(all_entities_dict)
									else:
										all_entities_dict['URI'] = entity.external_URI
										all_entities_dict['name'] = entity.surfaceForm
										all_entities_dict['type'] = ', '.join(entity.types["DBpedia"])
										other_entities.append(all_entities_dict)

						# parse markdown
						marked_text = ''
						for index, entity in enumerate(entities):
							final_index = len(entities) - 1
							word = entity['surfaceForm']
							offset = int(entity['offset'])
							link = entity['external_URI']
							offset_after = len(word) + offset
							if marked_text == '':
								text_before_word = raw_text[:offset]
							else:
								# text_before_word = marked_text[:new_offset]
								text_before_word = marked_text
							text_after_word = raw_text[offset_after:]
							if entity['support'] >= support_threshold:
								markup_token = '[' + word + '](' + link + ')'
							else:
								markup_token = '<span style="color: red;">' + word + '</span>'
							new_offset = offset + len(markup_token)

							if len(entities) == 1:
								marked_text = text_before_word + markup_token + text_after_word
							else:
								marked_text = text_before_word + markup_token
								if index == final_index:
									# marked_text = text_before_word + markup_token + text_after_word
									# marked_text = marked_text + markup_token + text_after_word
									marked_text = marked_text + text_after_word
								elif index+1 == final_index:
									next_word_offset = int(entities[index+1]['offset'])
									text_between = raw_text[offset_after:next_word_offset]
									marked_text = marked_text + text_between
								else:
									next_word_offset = int(entities[index+1]['offset'])
									text_between = raw_text[offset_after:next_word_offset]
									# text_between = raw_text[new_offset:next_word_offset]
									marked_text = marked_text + text_between

							html_marked_text = markdown.markdown(marked_text.lstrip())
							markup_data['chapters'][str(chapter.number)][str(paragraph.number)]['markup'] = html_marked_text
					else:
						html_marked_text = markdown.markdown(raw_text.lstrip())
						markup_data['chapters'][str(chapter.number)][str(paragraph.number)]['markup'] = html_marked_text
				else:
					raw_text = paragraph['text']
					html_marked_text = markdown.markdown(raw_text.lstrip())
					markup_data['chapters'][str(chapter.number)][str(paragraph.number)]['markup'] = html_marked_text

	place_df = pd.DataFrame(all_places)
	place_df = place_df.groupby(['URI','name','type']).name.count().reset_index(name="count")
	all_places = place_df.to_json(orient="records")

	return markup_data, all_places

@app.route('/text/<text_name>')
def show_nel_text(text_name):
	text_id = '/text/' + text_name
	text_metadata = admin.Text.objects.get(entity_id=text_id)
	nel_text = admin.nel.objects.get(internal_URI=text_metadata)
	markup_data, places = convert_to_markdown(nel_text)
	return render_template('show_nel.html', text=nel_text, text_id=text_id, text_name=text_name, markup_data=markup_data, places=places)

@app.route('/places')
def places():

	places = admin.Place.objects()
	parsed_places = places.to_json()

	# TODO: Update mentions to all placenames after each NEL scan.

	return render_template('places.html', places=parsed_places)

@app.route('/place/<place_name>')
def show_place(place_name):

	parsed_place_name = place_name.replace('_',' ')

	place = admin.Place.objects.get(name=place_name)
	parsed_place = place.to_json()

	texts = admin.Text.objects()

	mentioned_texts = []
	for text in texts:
		nel_text = admin.nel.objects.get(internal_URI=text)

		for chapter in nel_text.chapters:
			for paragraph in chapter.paragraphs:
				if "text" in paragraph:
					if "entities" in paragraph:
						if bool(paragraph["entities"]) == True:
							entities = paragraph["entities"]
							all_entities_dict = {}

							for entity in entities:
								if entity.surfaceForm == parsed_place_name:
									if "DBpedia" in entity.types:
										if "Place" in entity.types["DBpedia"] or "Location" in entity.types["DBpedia"] or "Settlement" in entity.types["DBpedia"] or "PopulatedPlace" in entity.types["DBpedia"]:
											# don't add duplicates to texts
											if len(mentioned_texts) > 0:
												for found_text in mentioned_texts:
													if found_text['title'] == text.title and found_text['entity_id'] == text.entity_id:
														pass
													else:
														text_dict = {}
														text_dict['entity_id'] = text.entity_id
														text_dict['title'] = text.title
														mentioned_texts.append(text_dict)
											else:
												text_dict = {}
												text_dict['entity_id'] = text.entity_id
												text_dict['title'] = text.title
												mentioned_texts.append(text_dict)


	return render_template('show_place.html', place_name=parsed_place_name, place=parsed_place, texts=mentioned_texts)

###################
# LINKED DATA API #
###################

# Provide GeoJSON for show_nel.html map
@app.route("/fetch_nel_geojson/text/<text_id>", methods=['GET'])
def fetch_nel_geojson(text_id):
	places = []
	# support_threshold = int(support_threshold)
	# text_id = int(text_id)

	text_id = '/text/' + text_id
	text_metadata = admin.Text.objects.get(entity_id=text_id)
	nel_text = admin.nel.objects.get(internal_URI=text_metadata)

	# helper function to collect places from text
	def add_record(places, entity):
		# is this first place?
		if len(places) == 0:
			place_dict = {
				'external_URI': entity['external_URI'],
				'internal_URI': entity['internal_URI'],
				'surfaceForm': entity['surfaceForm'],
				'support': entity['support'],
				'mentions': 1
			}
			print('Made the first record for', entity['surfaceForm'])
			places.append(place_dict)
			return places
		else:
			# if not the first place, check if the place is already added
			for current_place_dict in places:
				if current_place_dict['surfaceForm'] == entity['surfaceForm']:
					current_place_dict['mentions'] = current_place_dict['mentions'] + 1
					print(str(current_place_dict['mentions']) + ' mentions for', current_place_dict['surfaceForm'])
					return places
				else:
					place_dict = {
						'external_URI': entity['external_URI'],
						'internal_URI': entity['internal_URI'],
						'surfaceForm': entity['surfaceForm'],
						'support': entity['support'],
						'mentions': 1
					}
					print('Made the first record for', entity['surfaceForm'])
					places.append(place_dict)
					return places

	for chapter in nel_text.chapters:
		for paragraph in chapter.paragraphs:
			for entity in paragraph.entities:
				# if entity['support'] >= support_threshold:
				if "DBpedia" in entity.types:
					if "Place" in entity.types["DBpedia"]:
						places = add_record(places, entity)

	seq = [x['mentions'] for x in places]
	if len(seq) == 0:
		max_mentions = 0
	else:
		max_mentions = max(seq)
	if max_mentions > 100:
		marker_scale = 0.1
	elif max_mentions > 10:
		marker_scale = 1
	else:
		marker_scale = 10

	df = pd.DataFrame(places)
	del df['mentions']
	df = df.groupby(['surfaceForm']).mean()
	df = df.astype({'support': 'int'})

	# collect boundaries
	json_collection = []

	geocoded_places = admin.Place.objects().exclude('id')

	for place in places:
		if place['external_URI'].startswith('http://de.'):
			long_name = place['external_URI'].lstrip('http://de.dbpedia.org/resource/')
		else:
			long_name = place['external_URI'].lstrip('http://dbpedia.org/resource/')
		long_name = long_name.replace('_', ' ')
		for gc_place in geocoded_places:
			# if gc_place.name == place['surfaceForm'] or gc_place.name == long_name:
			if gc_place.URI == place['external_URI'] or gc_place.de_URI == place['external_URI']:
				geometry = gc_place.shape
				# TODO: use a relative scale for the marker.
				scaled_mentions = place['mentions'] * marker_scale
				avg_support = int(df.loc[place['surfaceForm']].support)
				json_feature = geojson.Feature(geometry=geometry, properties={"name": gc_place.name, "support": place['support'], "avg_support": avg_support, "scaled_mentions": scaled_mentions, "mentions": place['mentions']})
				json_collection.append(json_feature)

	feature_collection = geojson.FeatureCollection(json_collection)
	geojson_map = geojson.dumps(feature_collection)

	return Response(geojson_map, mimetype="application/json", status=200)
