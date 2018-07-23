/**
edge.js
*/

alertify.set('notifier','position', 'top-center');
alertify.set('notifier','delay', 10);

var _plan_ = {
	select_servers: function(key, value){
		$('[' + key + '="'+ value +'"]').prop('checked', !$('[' + key + '="'+ value +'"]').prop('checked'));
	},
	is_servers: function(project_name){
		var selected_servers = $('input[name="servers"]:checked').length;
		if(selected_servers  == 0){
			alertify.error("Please select servers, " + selected_servers + " server(s) selected !!");
		}
        else{
            var selected_server_list = [];
            var selected_servers = $('input[name="servers"]:checked').map(function(){selected_server_list.push($(this).val());});
            console.log(selected_server_list);
            alertify.prompt( 'Please specify reason for performing action ?', '', ''
               , function(evt, value) 
               { 
                if (value != '') {
                    _action_.reason(value,project_name,selected_server_list);
                    $('#take_action').click();
                } 
                else {
                    alertify.error('You cannot leave this field blank..');
                }
               }, function() { 
                    alertify.error('Cancelled');
            });
        }
	}
};

var _action_ = {
	show_data: function(description, duration, exception, batch_count, session, timestamp, starttime, endtime) {
		var d = "";
		d += "<li>Duration: " + duration + "s </li>";
		d += "<li>Batch count: " + batch_count + "</li>";
		d += "<li>Start time: " + unescape(starttime) + "</li>";
		d += "<li>End time: " + unescape(endtime) + "</li>";
		d += "<li>Timestamp: " + unescape(timestamp) + "</li>";
		if(exception && exception != "null") {
			d += "<li>Exception: " + unescape(exception) + "</li>";
		}
        if(session && session != "null" && session != "undefined") {
            d += "<li>Session: " + unescape(session) + "</li>";
        }
        alertify.alert()
        	.setContent(d)
        	.setHeader("<em>Task Info: " + description + "</em>")
            .set('padding',true)
        	.set({transition:'zoom'})
        	.show();
    },
    revoke_action: function(action_id) {
    	alertify.prompt(
    		'', '',
    		function(evt, value) {
    			if (value != '') {
    				alertify.success('Executing revoke on #' + action_id);
    				_action_.revoke(action_id);
    			} else {
    				alertify.error('Do specify the reason for revoking action #' + action_id);
    			}
    		},
    		function() {
    			//alertify.error("Cancel #" + action_id);
    		}
    	).setHeader("Are you sure ? REVOKE will STOP #" + action_id)
    	.set('message', 'Specify reason for cancelling <b>#' + action_id + '</b>')
    	.set('labels', {ok:'REVOKE!', cancel:'Naa!'})
    	.set('padding',true)
    	.set({transition:'zoom'});
    },
    revoke: function(action_id){
    	$.getJSON({
            url: 'revoke/',
        }).done(function(data){
            //console.log(data);
            if($("#action_status").text() != data.status){
                $("#action_status").text(data.status);
                $("#action_status").removeClass("label-default");
                $("#action_status").addClass("label-danger");
            }
        });
    },
    reason: function(value,project_name,servers){
        console.log(servers);
        $.ajax({
            type: "POST",
            url: "/space/wizard/update_description/api/",
            data: {
            "description": value,
            "project_name": project_name,
            "servers": servers.join()
            },
            success: function(d) {
                console.log(d);
            },
            error: function (request, status, error) {
            alertify.error('Unable to update description');
            }
        });
    }
}

var _wizard_ = {
    validate: function() {
        try{
            if($("#id_config").val() != undefined){
                $.parseJSON($("#id_config").val());
            }
            return true;
        } catch (error) {
            alertify.error(error.message);
            return false;
        }
    }
}
