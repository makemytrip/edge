from django.template.defaulttags import register

import logging, json, datetime


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def get_json(dictionary):
    return json.dumps(dictionary, indent=4, sort_keys=True)


@register.filter
def get_int(value):
    return int(value)

@register.filter
def replace_char(value):
    return value.replace("_"," ")

@register.filter
def get_action_time(action_info):

	timestamp = action_info.timestamp
	countdown = action_info.config_dict().get('countdown', 10)
	return timestamp + datetime.timedelta(seconds=countdown)
