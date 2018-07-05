## [Edge: Deployment Framework](/)

### Deployment strategies at scale using Edge at MakeMyTrip
> Reliable, Robust, Rapid and Scalable approach for deployment automation

#### Contents
* [Features](#features-edge-framework)
* [Architecture](#architecture)
* [Terminologies](#terminologies)
* [Configuring an Environment](#configuring-an-environment)
* [Configuring a Project](#configuring-a-project)
* [Remote command execution](#remote-commands-execution)
* [Configuring the application](#configuring-the-application)
* [Logging to ElasticSearch](#centralized-logging-to-elasticsearch)
* [Testing the application](#testing-the-application)
* [Hosted REST APIs](#hosted-restful-ap)

#### Features: Edge Framework

* __Personalization__: Team or role based personalization support i.e. no more cluttered dashboard.
* __Multi Eco-system__ support i.e. DC, Cloud, Micro-Services & other custom deployments
* No pre defined scope(s) i.e. __flexible orchestrations__
* __Agentless__: hence no additional process is required to run over production machine.
* Configuration: minimal configuration as code.
* Horizontal scalibility support.
* Edge application is Docker-ized.


#### Architecture

![arch image](static/images/arch.png)

#### Terminologies

Please do keep in mind of below terms as these will be helpful in understanding the application.

* __Space__

> Space is what we refer to a lob. For example Payments, Hotels, Flights etc. will be referred as a `Space`.
>
> User ACLs are set at Space level i.e. will assign respective roles to DL on a particular Space.
>
> This is an important piece in personalization and correct authorization. Many reports can be provisioned at Space level.
>
> Also users will be fettered at Space level this will ensure that only relevant folks of a Lob have rights on respective Space(s).

* __Environment__

> Env. refers to infra + application metdata & configs. For ex:- DC-Tomcat, AWS-Tomcat, DC-Services

* __Project__

> Individual project level metadata & configs will be kept in a proper structure. These configuration will be utilized at the time of performing deployment or restart tasks.

* __Scripts__

> Interpretation of different deployment strategies will be written in deployment scripts that will be mapped to a respective environments.

* __Utlities__

> Utility classes to perform integrations like Canary or Jira & implement fundamentals like staggered deployments that are readily available to scripts.



#### Configuring an environment

Environment configuration are important placeholders for defining a project. Values of these placeholders defined under Environment will be considered while deployment or restart actions. These properties can & in some cases *must* be overriden from project configuration.


```json
{
	"server_info": "pool_info",
	"member_session_wait_time": 300,
	"repo_dir": "/opt/mmtrepos"
}
```

#### Configuring a project

A project or component as we call it in our CI pipeline will be associated with a `Space` and an `Env`. Plus it will have some configuration that will be required to identify resources and perform actions.

```json
{
	"version": "application-version.tar.gz",
	"pool_info": {
		"MUM": [{
			"inpool_threshold": 0,
			"pool_name": "pool1"
		}],
		"NEW_CHN": [{
				"inpool_threshold": 10,
				"pool_name": "pool1"
			},
			{
				"inpool_threshold": 10,
				"pool_name": "pool2"
			}
		]
	},
	"stop_command": "/etc/init.d/mmtwebd stop",
	"start_command": "/etc/init.d/mmtwebd start",
	"is_staggered": true,
	"is_canary": true,
	"member_session_wait_time": 600,
	"bizeye_folder": "<FTP_FOLDER>",
	"context_dir": "<context_dir>"
}
```

#### Remote commands execution


```

Remote shell commands will be executed using Python [Fabric](http://docs.fabfile.org/en/1.13/index.html)

In our current implementation we are using `.ssh/config` from the system itself for generating ssh user login enviornment.

Please do set `FABRIC_USER_PASSWORD` in system enviornment. That is keeping sensitive credentials out of the application.

##### Usage for Fabric class

Any command execution will done in parallel i.e. it will require list of hosts and the command at the time instantiating the `FabricHandler` class.

Output of for `exec_remote_command` will be a dict having below structure

```python
from orchestration.utils.fabric_handler import FabricHandler

FabricHandler(hosts=['s1', 's2'], command="hostname").exec_remote_command()

{'s1': {'hostname': (0,
   True,
   ['s1-hostname'])},
 's2': {'hostname': (0,
   True,
   ['s2-hostname'])}}

```

##### Sanitizing commands before remote execution

As implementation of Fabric is purely in python and there can be chances where user can run critical commands like `rm -rf /` over remote servers. Hence, have added a sanity check for the commands before executing the same over the remote server.

#### Configuring the application

Please read [project configuration](/space/project_config) for setting up the application for the first time.

#### Centralized logging to ElasticSearch

```diff
+ Better log management & enhanced cluster support
```

Logging for each `Action` performed using Edge is logged in ElasticSearch.

Every data being logged in ES will have a `correlation` key that will uniquely identify the logs. This data will be displayed over the UI as well.

Basic logging will simply log status of the executed method on a server. Will provide detailed logging per task performed in a method in a different ES index along with the same correlation id that will help in fetching the information on demand.

_This way we will be able to move away from local File based logging that is major pain point for running the application in cluster mode_


#### Testing the application

```
python manage.py test
Creating test database for alias 'default'...
System check identified some issues:

WARNINGS:
?: (urls.W001) Your URL pattern '^$' uses include with a regex ending with a '$'. Remove the dollar from the regex to avoid problems including URLs.

System check identified 1 issue (0 silenced).
.
----------------------------------------------------------------------
Ran 1 test in 4.815s

OK
Destroying test database for alias 'default'...

```

#### Hosted RESTful APIs


##### Deploy or Restart action

Endpoint

```
http://edge.mmt.com/space/<space_name>/<project_name>/<action>/
```

Payload

```json
{
	"servers": ["server1", "server2", "server3"],
	"user": "<user id>",
	"countdown": 10
}
```

Response

```json
{
	"action_id": <task_id>,
	"project": "project_name"
}
```
