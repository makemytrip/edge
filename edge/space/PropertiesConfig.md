## [Edge: Automation Framework](/)

#### Properties Config

Below properties must be added in ProjectConfigs from the Admin page.

``` yaml
 lbhost: lbmanager.mmt.com
 lbuser: edge
 lbtimeout: 60

 es_host: lbmanager.mmt.com:9200
 es_timeout: 5
 es_retries: 2

 es_index: __import__('datetime').datetime.now().strftime("edge-basic-%Y-%m-%d")
 es_detail_index: __import__('datetime').datetime.now().strftime("edge-detail-%Y-%m-%d")
 es_read_index: edge-basic-*
 es_read_detail_index: edge-detail-*
 es_read_count = 100

 member_session_wait_time: 900

 env_prefix: { "MUM" : "x.x", "NEW_CHN" : "x.x", "GGN" : "172.16" }

 staggered_batch_config: {'0':'Others','1': '100%', '2': '50%,100%', '4':'25%,50%,100%', '8':'10%,25%,50%,100%'}

 bizeye_url: {'MUM':'bizeye.mmt.mmt:1234','NEW_CHN':'bizeye.mmt.mmt:1234'}

 es_delete_template: {"query":{"bool" : { "must" : [{ "match" : {"correlation":%(correlation)s }}, %(delete_query)s ]}}}

 canary_schedule_api: http://canary.mmt.mmt/tanzin/schedulemetriccomparison

```

Below plans must be added in Plans from Admin page.

```yaml

restart: ['stop', 'start']
deploy: ['stop', 'install', 'start']

```
##### [Back to ReadMe](/space/readme)
