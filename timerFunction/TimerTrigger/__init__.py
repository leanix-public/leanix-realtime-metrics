from os import environ
import datetime
import logging
import json
import lxpy
import datetime
import requests
import locale
import pandas as pd

import azure.functions as func

def getAccess():
    with open('accessT.json') as json_file:
        data = json.load(json_file)
        return data


config = lxpy.ClientConfiguration(
    base_url=environ.get('BASE_URL', getAccess()['host']),
    api_token=environ.get('API_TOKEN', getAccess()['apitoken'])
)
metrics = lxpy.Metrics(config)

auth_url = 'https://' + config.base_url + '/services/mtm/v1/oauth2/token'
request_url = 'https://' + config.base_url + '/services/integration-api/v1/'

# Get the bearer token - see https://dev.leanix.net/v4.0/docs/authentication
response = requests.post(auth_url, auth=('apitoken', config.api_token),
                         data={'grant_type': 'client_credentials'})
response.raise_for_status()
header = {'Authorization': 'Bearer ' + response.json()['access_token'], 'Content-Type': 'application/json'}


def startRun(run):
    response = requests.post(url=request_url + 'synchronizationRuns/' + run['id'] + '/start?test=false', headers=header)


def status(run):
    response = requests.get(url=request_url + 'synchronizationRuns/' + run['id'] + '/status', headers=header)
    return (response.json())


def createRun(content):
    data = {
        "connectorType": "TimeBasedMetrics",
        "connectorId": "metricKPI",
        "connectorVersion": "1.0.0",
        "lxVersion": "1.0.0",
        "description": "Imports Metric data into LeanIX",
        "processingDirection": "inbound",
        "processingMode": "partial",
        "content": content
    }

    print(data)
    response = requests.post(url=request_url + 'synchronizationRuns/', headers=header, data=json.dumps(data))
    print(response.json())
    return (response.json())


def createContent(measurement, fieldKey, fieldValue, tagKey, tagValue, id):
    time = str(datetime.datetime.now().strftime("%Y-%m-%d") + "T00:00:00.000Z")
    content = {
        "type": "Metrics",
        "id": id,
        "data": {"measurement": measurement, "fieldKey": fieldKey, "fieldValueNumber": fieldValue, "time": time, "tagKey": tagKey, "tagValue": tagValue}
    }
    return content


def call(query):
    data = {"query" : query}
    json_data = json.dumps(data)
    response = requests.post(url='https://' + config.base_url + '/services/pathfinder/v1/graphql', headers=header, data=json_data)
    response.raise_for_status()
    return response.json()


# Read all existing Application - IT Component relations
def exportCosts():
    query = """
  {
    allFactSheets(factSheetType: Application) {
      edges {
        node {
          id
          displayName
          ... on Application {
            relApplicationToITComponent {
              edges {
                node {
                  id
                  costTotalAnnual
                  factSheet {
                    id
                    displayName
                  }
                }
              }
            }
          }
        }
      }
    }
  }
  """
    return query

def getFactSheetsByType(type):
    query = """
    {
      allFactSheets(filter: {facetFilters: [{facetKey: "FactSheetTypes", keys: [""" + "\"" + type + "\"" + """]}]}) {
        totalCount
        edges {
          node {
            id
            displayName
            type
          }
        }
      }
    }
    """
    return query


def getAllFacets():
    query = """
    {
      allFactSheets{
        filterOptions {
          facets {
            facetKey
            results {
              name
              key
            }
          }
        }
      }
    }
    """
    return query


def createFactSheetCountByTypeKPI():
    response = call(getAllFacets())
    data = response['data']['allFactSheets']['filterOptions']['facets']
    results = data[0]['results']
    content = []
    i = 0
    for result in results:
        response = call(getFactSheetsByType(result['name']))
        print(result['name'] + str(response['data']['allFactSheets']['totalCount']))
        content.append(createContent('FactSheetCountByType', result['name'], str(response['data']['allFactSheets']['totalCount']), 'factSheetFacet', 'Count', str(i)))
        i = i + 1
    run = createRun(content)
    startRun(run)


createFactSheetCountByTypeKPI()