## STORM Deploy: storm.py

storm_deploy is a script mapped to `storm` env. Below are the parameters that are recognized by this script

##### `version*`

Deliverable that will be installed at deploy action.

##### `nimbus_server_list*`

DC wise configuration of Nimbus Host.

```json
"pool_info": {
	    "CMMT": [ {
                "port": "8080",
                "server": "x.x.x.x",
                "version": "0.9.6"
            }
        ],
        "MUM": [ {
                "port": "8080",
                "server": "x.x.x.x",
                "version": "0.9.6"
            }, {
                "port": "8080",
                "server": "x.x.x.x",
                "version": "0.9.6"
            }
        ]
}
```

##### `topology_name*`
```
"topology_name": default to project name.
```

##### `storm_dir*`
```
"storm_dir": "/opt/storm"
```

##### `kill_wait_time`

The time (in seconds) required while killing the topology in the cluster.

`default = 30`

##### `class_name`
```
class_name = topology.OpenTSDBWriterTopology
```

##### `class_params`
```
default null
```

##### `java_params`
```
java_params = -DzkConfigHost=x.x.x.x:2181 -DzkConfigNode=/OpenTSDBWriterTopology -DzkConfigFile=/OpentsDBWriterTopology.properties
```

##### `md5_checksum`
Whether to do checksum of downloaded jar file or not.

`default = false`

