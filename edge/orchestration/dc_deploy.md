## DC Deploy: dc_deploy.py

dc_deploy is a script mapped to `dc-tomcat-f5` env. Below are the parameters that are recognized by this script

##### `version*`

Deliverable that will be installed at deploy action.

##### `pool_info*`

DC wise configuration of pool & pool strength.

```json
"pool_info": {
	"MUM": [{
		"inpool_threshold": 70,
		"pool_name": "sitemum_kafka-data.mmt.mmt_l4_pool"
	}],
	"NEW_CHN": [{
			"inpool_threshold": 70,
			"pool_name": "c_kafka-mmt.mmt.mmt_l4_pool"
		},
		{
			"inpool_threshold": 70,
			"pool_name": "c_kafka-common.mmt.mmt_l4_pool"
		}
	]
}
```

##### `stop_command*`
```json
"stop_command": "/etc/init.d/mmtwebd stop",
```
##### `start_command*`

Example

```json
"start_command": "/etc/init.d/mmtwebd start",
```

##### `is_staggered`

default = false

##### `is_canary`

default = false

##### `member_session_wait_time`

Wait time for session polling from F5. 

session polling method will exit if # of session are 0 or member session wait time is over, which ever event occurs first.

default = 300
unit = seconds