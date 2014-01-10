var op_clock = 0;
var session = 0;
var varid_to_name = {};
var id_to_widget = {};
var widget_to_convert = {};
var cameras = [];
var last_time = 0;
var last_camera_update = 0;

var GOOD = 0;
var BAD = 2;
var UGLY = 1;
var state = ["good", "ugly", "bad"];
var text_state = ["", "warning", "error"];
var alarms = {}
var buttons = [];
var known_widgets = {};
var _request_still_open = false;

$(function() {
  $( "#sortable" ).sortable();
  $( "#sortable" ).disableSelection();
});

function toggle_alarms(button) {
  $("#klaxon")[0].muted = !button.checked
}

function toggle(button) {
    set_config(buttons[button.id], button.checked);
}

function to_int(_float) {
    var f = parseFloat(_float);
    return f.toFixed(0);
}

function to_date(_number) {
    console.log("Converting " + _number + " to a date");
    var i = parseInt(_number);
    console.log(new Date(i*1000));
    return new Date(i*1000).toString();
}

function trim_float2(_float) {
    var f = parseFloat(_float);
    return f.toFixed(2);
}

function trim_float5(_float) {
    var f = parseFloat(_float);
    return f.toFixed(5);
}

function bytes_to_string(_bytes) {
    var bytes = parseInt(_bytes);
    knownSizes = [[" PB", 1024*1024*1024*1024*1024],
                  [" TB", 1024*1024*1024*1024],
                  [" GB", 1024*1024*1024],
                  [" MB", 1024*1024],
                  [" KB", 1024]]
    for (var i=0; i<knownSizes.length; i++) {
	if (bytes/knownSizes[i][1] > 0.8) {
	    return (bytes/knownSizes[i][1]).toFixed(2) + knownSizes[i][0];
	}
    }
    return bytes + " B";
}

function _make_toggle_button(id, label, toggled) {
    var state = "ui-state-default"
    if (toggled == true)
	state = "ui-state-active"
    return '<input class="ui-helper-hidden-accessible" type="checkbox" id="'+ id + '" onclick="toggle(this)" aria-disabled="false"/><label class="ui-button ui-widget '+state+' ui-button-text-only ui-corner-left" for="'+id+'">'+label+'</label>';
}

function get_config(parameter, onsuccess) {
    console.log("get_config(" + parameter + ")");
    $.getJSON("/cfg/get?param=" + parameter, null, onsuccess);
}

function set_config(parameter, value) {
    $.ajax("/cfg/set?param=" + parameter + "&value=" + value);
}

function widget_init(control_tag) {
    if (control_tag != undefined) {
	html = '<span class="ui-buttonset" id="alarmbuttons">';
	html += '<input class="ui-helper-hidden-accessible" type="checkbox" id="mute" onclick="toggle_alarms(this)"  aria-disabled="false"/><label class="ui-button ui-widget ui-state-default ui-button-text-only ui-corner-left" for="mute">Alarms</label>';
	html += '<button id="save">Save</button><button id="load">Load</button>';
	html += "</span>";
	$("#" + control_tag).append(html);
    }

    $("body").append('<audio id="klaxon" class="hidden"><source src="_BASE_PATH_klaxon.ogg" type="audio/ogg"></audio>');
    $("body").append('<div id="alarms" class="hidden"></div>');
    $("body").append('<div id="save_alarms" class="hidden"></div>');
    $("body").append('<div id="load_alarms" class="hidden"></div>');
    $("#alarms").removeClass("hidden").hide();
    $("#klaxon")[0].muted = true;
    window.setInterval(monitor_state, 500);         /* .5 second */
    $("#save_alarms").removeClass("hidden").hide();
    $("#save_alarms").append(get_save_alarms_html());
    $("#load_alarms").removeClass("hidden").hide();
    $("#load_alarms").append(get_load_alarms_html());
    
    $(function() {
	$( "#mute" ).button();
	$( "#save" ).button().click(function() {
	    $("#save_alarms").dialog({width:500, height:300, modal:true, buttons: {Cancel: function() {$(this).dialog("close");}, Save: function() { $(this).dialog("close"); save_alarms()}}});
	});
	$( "#load" ).button().click(function() {
	    load_alarm_list();
	    $("#load_alarms").dialog({width:500, height:300, modal:true, buttons: {Cancel: function() {$(this).dialog("close");}, Load: function() {$(this).dialog("close"); load_alarms();}}});
	});
	$("#alarmbuttons").buttonset();
    });
}

function save_alarms() {
    if ($("#alarm_name").val() == "") {
	alert("Must have a name");
	return;
    }
    
    var data = {"alarms":alarms,
		"widgets":get_state()};

    $.ajax("/item/add?key=" + $('#alarm_name').val() + "&item=" + JSON.stringify(data));
}

function load_alarm_list() {
    $.getJSON("/item/list", function(data) {
	for (var i=0; i<data.keys.length; i++) {
	    $("#selected_alarm").append("<option>" + data.keys[i] + "</option>");
	}
    });    
}
function load_alarms() {
    var alarm = $("#selected_alarm").val();

    $("#alarm_name").val(alarm);
    $.ajax("/sessionclr?session=" + session, {complete: function() {

	$.getJSON("/item/get?key=" + alarm, function(data) {
	    $("#sortable").html("");
	    // need new session I guess
	    alarms = data.alarms;
	    // Add the widgets too
	    for (var i=0; i<data.widgets.length; i++) {
		var id = data.widgets[i][0];
		var c = data.widgets[i][1];
		//console.log("ID" + id);
		id = id.replace("_", ".");
		//console.log(known_widgets);
		if (known_widgets[id] != undefined) {
		    var widget = generate_widget(id, known_widgets[id], c);
		    add_widget(widget);
		}
	    }
	    //reset();
	    use_session(session);
	});    
    }});
}

function to_id(full_name) {
    return full_name.replace(/[\.() ]/g, '_');
}

if (typeof String.prototype.startsWith !== 'function') {
    String.prototype.startsWith = function (str) {
	return this.slice(0, str.length) === str;
    };
}

if (typeof String.prototype.endsWith !== 'function') {
    String.prototype.endsWith = function (str) {
	return this.slice(-str.length) === str;
    };
}

function sound_alarm(sound_it) {
      var klaxon = document.getElementById("klaxon");
      klaxon.loop = true;
      if (sound_it) { 
        if (klaxon.paused == true) {
           klaxon.play();
        }
      } else if (klaxon.paused == false) {
        klaxon.pause();
        klaxon.currentTime = 0;
      }
}

function get_save_alarms_html() {
    html = "<h3>Save alarms</h3>";
    html += "Name: <input id='alarm_name'>";
    return html;
}

function get_load_alarms_html() {
    html = "<h3>Load alarms</h3>";
    html += "<select id='selected_alarm'></select>";
    // Load alarms from db.
    return html;
}

function close(widget) {
    $("#" + widget).addClass("hidden");
}

function add(widget) {
    $("#" + widget).removeClass("hidden");
}    

function get_base_widget(channel, instrument, body, wclass, extra, log_module) {
    var id = to_id(channel + "_" + instrument);
    var state_id = id + "_state";
    var html = "<li id='" + id + "' class='" + wclass + " ui-widget-content'>";
    if (channel.length > 17) 
	channel = "..." + channel.slice(-17);
    if (channel == "") // Ensure that we can hit it
	channel = "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"; 
    html += "<div class='widget_channel bad' id='" + id + "_s'><a href='javascript:show_alarms(\"" + id +"_s\",\""+state_id+"\")' title=''>" + channel + "</a><a href='javascript:close(\"" + id + "\")' class='right_float'>X</a></div>";
    html += "<div class='ui-widget-header'>";
    if (log_module) 
	html += "<a href='log.html?module=" + log_module + "' target='log'>" + instrument + "</a>"
    else
	html += instrument;
    html += "<div class='inline right_float'><a href='javascript:toggleExpand(\"" + id + "\", \"small\")'> .</a><a href='javascript:toggleExpand(\"" + id + "\", \"medium\")'>o</a><a href='javascript:toggleExpand(\"" + id + "\", \"big\")'>O</a></div></div>";
    body = "<div id='" + id + "_state' class='right_float'></div>" + body;
    if (wclass == "small") 
        html += "<div id='" + id + "_body' class='hidden'>" + body + "</div>";
    else 
        html += "<div id='" + id + "_body'>" + body + "</div>";
    if (wclass == "big")
        html += "<div id='" + id + "_extra' class='right_float'>" + extra + "</div>";
    else
	html += "<div id='" + id + "_extra' class='right_float hidden'>" + extra + "</div>";
    html += "</li>";
    return html;
}

function update_state(info) {

    var id = "#" + to_id(info.widget);
    var value = info.value;
    if (info.convert) {
	value = info.convert(value);
    }
    if (info.name == "state") {
	var parent = "#" + to_id(info.channel + "_s");
	// If this is a state tag, we color it according to what we know
	var c = "warning";
	var c2 = "ugly";
	if (value == 'up' || (value == 'running') || (value == 'online')) {
            c = "ok";
            c2 = "good";
	} else if (value == 'down' || (value == 'failed') || (value == 'stopped') || (value == 'offline') || (value == 'initializing') || (value == 'starting') || (value == 'na')) {
            c = "error";
            c2 = "bad";
	}
	$(id).removeClass("ok").removeClass("error").removeClass("warning").addClass(c);
	$(parent).removeClass("good").removeClass("bad").removeClass("ugly").addClass(c2);
	$(parent).attr("title", value);
    }
    $(id).html(value);
}

function add_widget(widget, instrument) {
    //    $("#wc").append(widget);
    $("#sortable").append(widget);
    $("#" + instrument + "_extra").removeClass("hidden").hide();
    $("#" + instrument).tooltip();
}

function get_camera_widget(name, info) {
    var s = splitChannel(name);
    var w = get_base_widget(s[0], s[1], "");
    return w;
}

function _p_add(widget, name, param, text, convert) {
    var id = to_id(name + "_" + param);
    widget_to_convert[id] = convert;
    add_param(id, name, param);
    var html = "<a href='javascript:show_alarms(\"" + widget + "\", \"" + id + "\")'>" +text + "</a> <div class='inline' id='" + id + "'></div> ";
    return html;
}

function generate_widget(name, info, c) {
    known_widgets[name] = info;
    // Figure out if this is a specialized widget and create that, or return a generic one
    add_param(name + ".state", name, "state");

    var s = splitChannel(name);
    var wchannel = s[0];
    var wname = s[1];
    var log_module = null;
    var body = "";
    var extra = "";
    var wid = to_id(name);
    // Camera
    if (wname.startsWith("Camera")) {
        log_module = "UAVCamera";
	var pt = to_id(name + "_pt");
	body = _p_add(wid, name, "PicturesTaken", "Pictures taken:") + "<br>";
	body += _p_add(wid, name, "errors", "Errors:") + "<br>";
	body += _p_add(wid, name, "model", "Model:") + "<br>";
	body += "<a id='" + wname +"_ref' target='img' href=''><img id='" + wname + "_pic'/></a>";
	extra = _make_toggle_button(to_id(wname + "_tgl"), "Enable", false);
	buttons[wname + "_tgl"] = "Instruments.Camera.Enabled";
	cameras.push({"widget":wname, "instrumentid":0}); // use instrument ID 0, which is default prefix for camera
    }
    
    // Channel checkers 
    else if (wname.endsWith("ChannelChecker")) {
        log_module = "ChannelChecker";
	body = _p_add(wid, name, "bytes_received", "Received:", bytes_to_string) + "<br>";
	body += _p_add(wid, name, "bytes_sent", "Sent:", bytes_to_string) + "<br>";
	body += "<hr>";
	body += _p_add(wid, name, "rtt_avg", "RTT:") + "<br>";
	body += _p_add(wid, name, "packet_loss", "Packet loss:") + "<br>";
    }

    // Dialers
    else if (wchannel == "Network.Dialer") {
	log_module = "Dialer";
	body = _p_add(wid, name, "ip", "IP:") + "<br>";
	body += _p_add(wid, name, "ppp_interface", "Iface:") + "<br>";
	body += "<hr>";
	body += _p_add(wid, name, "default_gateway", "GW:") + "<br>";
	body += _p_add(wid, name, "modem", "Modem:") + "<br>";
	body += _p_add(wid, name, "port", "Port:") + "<br>";
	body += _p_add(wid, name, "connections_initiated", "Initiated:") + "<br>";
	body += _p_add(wid, name, "connections_lost", "Lost:") + "<br>";
    }

    // Auto pilot
    else if (wname.startsWith("AutoPilot")) {
	log_module = "AutoPilot";
	body = _p_add(wid, name, "bytes_received", "Received:", bytes_to_string) + "<br>";
	body += _p_add(wid, name, "bytes_sent", "Sent:", bytes_to_string) + "<br>";
    }
    // IMU & GPS
    else if ((wname == "IMU") ||(wname == "GPS")) {
	if (wname === "IMU") log_module = "NativeIMU";
	if (wname === "GPS") log_module = "NMEA";
	body = _p_add(wid, name, "lat", "Lat:", trim_float5) + "<br>";
	body += _p_add(wid, name, "lon", "Lon:", trim_float5) + "<br>";
	body += _p_add(wid, name, "alt", "Alt:", trim_float2) + "<br>";
    body += _p_add(wid, name, "hdg", "Heading:", trim_float2) + "<br>";
    body += _p_add(wid, name, "spd", "Speed:", trim_float2) + "<br>";      
	body += "<hr>";
	body += _p_add(wid, name, "fix_mode", "Fix:") + "<br>";      
    }
    else if (wname == "ArduIMU") {
	body = _p_add(wid, name, "lat", "Lat:", trim_float5) + "<br>";
	body += _p_add(wid, name, "lon", "Lon:", trim_float5) + "<br>";
	body += _p_add(wid, name, "alt", "Alt:", trim_float2) + "<br>";
    body += _p_add(wid, name, "cog", "Heading:", trim_float2) + "<br>";
    body += _p_add(wid, name, "sog", "Ground speed:", trim_float2) + "<br>";      
	body += "<hr>";
	body += _p_add(wid, name, "fix", "Fix:") + "<br>";      
    }

    // Power supply
    else if (wname == "PowerSupply") {
	log_module = "PowerSupply";
	body = _p_add(wid, name, "battery", "Bat:") + "<br>";
	body += _p_add(wid, name, "load_5v", "Load 5v:");
	body += _p_add(wid, name, "load_24v", "24v:") + "<br>";
	body += "<hr>";
	body += _p_add(wid, name, "payload", "Payload:") + "<br>";
	body += _p_add(wid, name, "camera", "Camera:") + "<br>";
	body += _p_add(wid, name, "modem", "Modem:") + "<br>";
	body += _p_add(wid, name, "radio_modem", "Radio:") + "<br>";
	body += _p_add(wid, name, "strobe", "Strobe:") + "<br>";
	body += _p_add(wid, name, "ignition", "Ignition:") + "<br>";
    }
    // System control
    else if (wname == "SystemControl") {
	log_module = "SystemControl";
	body = _p_add(wid, name, "cpu_idle", "CPU idle:", trim_float2) + "<br>";
	body += _p_add(wid, name, "Virtual device.temp1", "Temp:", trim_float2) + "<br>";
	body += _p_add(wid, name, "swap_used", "Swap:", bytes_to_string) + "<br>";
	body += _p_add(wid, name, "disk_available", "Disk:", bytes_to_string) + "</br>";
	body += _p_add(wid, name, "uptime", "Uptime:") + "</br>";

	// Add toggles for processes
    }
    // System info
    else if (wname == "SystemInfo") {
	log_module = "SystemInfo";
	body = _p_add(wid, name, "cpu_idle", "CPU idle:") + "<br>";
	body += _p_add(wid, name, "ISA adapter.Core 0", "Temp:", trim_float2) + "<br>";
	body += _p_add(wid, name, "swap_used", "Swap:", bytes_to_string) + "<br>";

    }
    else if (wname == "Housekeeping") {
	log_module = "HouseKeeping";
	body = _p_add(wid, name, "rpm", "RPM:", to_int) + "<br>";
	body += _p_add(wid, name, "Fuel level (mm)", "Fuel:", trim_float2) + "<br>";

	body += "<div class='ui-widget-header'>Temps:</div>";
	body += _p_add(wid, name, "Payload temperature", "Payload:", trim_float2) + "<br>";
	body += _p_add(wid, name, "Ambient temperature", "Ambient:", trim_float2) + "<br>";
	body += _p_add(wid, name, "Engine temperature", "Engine:", trim_float2) + "<br>";
	body += _p_add(wid, name, "Engine inlet temperature", "Inlet:", trim_float2) + "<br>";
	body += _p_add(wid, name, "PSU cooling air temperature", "PSU:", trim_float2) + "<br>";
    }
    else if (wname == "BaseStation") {
	body = _p_add(wid, name, "current_connection", "Connection:");
    }
    else if (wchannel.endsWith("DialIn")) {
	body = _p_add(wid, name, "bytes_up", "Sent:", bytes_to_string) + "<br>";
	body += _p_add(wid, name, "bytes_down", "Received:", bytes_to_string);

	extra = _p_add(wid, name, "ip", "IP:") + "<br>";
	extra += _p_add(wid, name, "ppp_interface", "IF:") + "<br>";
    }
    else if (wname == "DataRelay") {
	log_module = "DataRelay";
	body = _p_add(wid, name, "bytes_to_destination", "Sent:", bytes_to_string) + "<br>";
	body += _p_add(wid, name, "bytes_from_destination", "Received:", bytes_to_string) + "<br>";
	body += _p_add(wid, name, "current_forward_host", "Target:");
	body += "<hr>";
	body += _p_add(wid, name, "current_forward_port", "Target port:") + "<br>";
	body += _p_add(wid, name, "bytes_from_source", "From source:", bytes_to_string) + "<br>";
	body += _p_add(wid, name, "bytes_to_source", "To source:", bytes_to_string) + "<br>";
	body += _p_add(wid, name, "input", "Input:") + "<br>";
    }
    else if (wname == "RemoteStatusInfo") {
	log_module = "RemoteStatusInfo";
	body = _p_add(wid, name, "Remote.lat", "Lat:", trim_float5);
	body += _p_add(wid, name, "Remote.lon", "Lon:", trim_float5);
	body += _p_add(wid, name, "Remote.alt", "Alt:", trim_float2) + "<br>";
	body += _p_add(wid, name, "Remote.heading", "Heading:", trim_float2) + "<br>";
	body += _p_add(wid, name, "Remote.speed", "Speed:", trim_float2) + "<br>";      
	body += _p_add(wid, name, "Remote.battery", "Battery:") + "<br>";      
	body += _p_add(wid, name, "Remote.rpm", "RPM:") + "<br>";      

	body += _p_add(wid, name, "Remote.num", "Counter:") + "<br>";
	c = "medium";
    }
    else if (wname == "SpeedTest") {
	body = _p_add(wid, name, "bytes_received", "Received:", bytes_to_string) + "<br>";
	body += _p_add(wid, name, "lost_packets", "Lost packets:", bytes_to_string) + "<br>";
	body += _p_add(wid, name, "udp", "UDP:") + "<br>";
	body += _p_add(wid, name, "tcp", "TCP:") + "<br>";
    }
    else if (wname == "Trios") {
	log_module = "TriOS";
	body = _p_add(wid, name, "num_samples-02", "Up:") + "<br>";
	body += _p_add(wid, name, "num_samples-04", "Down:") + "<br>";
	body += "<div class='ui-widget-header'>Bad:</div>";
	body += _p_add(wid, name, "bad_samples-02", "Up:") + "<br>";
	body += _p_add(wid, name, "bad_samples-04", "Down:") + "<br>";
    }
    else if (wname == "UEye") {
	log_module = "ueye";
	body = _p_add(wid, name, "imagesCaptured", "Captured:") + "<br>";
	body += _p_add(wid, name, "actualFPS", "FPS (actual):", trim_float2) + "<br>";
	body += "<hr>";
	body += _p_add(wid, name, "imagesSaved", "Saved:") + "<br>";
	body += _p_add(wid, name, "savedFPS", "FPS (saved):") + "<br>";
    }
    else if (wname == "BatteryMonitor") {
	body = _p_add(wid, name, "Voltage", "Voltage", trim_float2) + "V<br>";
	body += _p_add(wid, name, "Current", "Current", trim_float2) + "A<br>";
	body += _p_add(wid, name, "Charge", "Charge") + "%<br>";
	body += _p_add(wid, name, "Consumed", "Consumed") + "Ah<br>";
	body += _p_add(wid, name, "Left", "Left") + "h<br>";
    }
    else if (wname.startsWith("Hauppauge")) {
        log_module = "Hauppauge";
	var pt = to_id(name + "_pt");
	body = _p_add(wid, name, "bytes_read", "Recorded:", bytes_to_string) + "<br>";
	body += "<a id='" + wname +"_ref' target='img' href=''><img id='" + wname + "_pic'/></a>";
	cameras.push({"widget":wname, "instrumentid":40}); // use instrument ID 40, which is default prefix for Hauppauge
    }

    else if (wname.startsWith("GatherRemotePictures")) {
        log_module = "GatherRemotePictures";
	var pt = to_id(name + "_pt");
	body = _p_add(wid, name, "images_received", "Received:") + "<br>";
	body += _p_add(wid, name, "bytes_received", "Received:", bytes_to_string) + "<br>";
	body += _p_add(wid, name, "last_timestamp", "Last time:", to_date) + "<br>";
	body += "<a id='" + wname +"_ref' target='img' href=''><img id='" + wname + "_pic'/></a>";
	cameras.push({"widget":wname, "instrumentid":125, "q":1}); // use instrument ID 125, default for remote
	c = "big";
    }
    else if (wname.startsWith("irTrigger")) {
	body = _p_add(wid, name, "PicturesTaken", "Taken:") + "<br>";	
    }
    else if (wname.startsWith("Laser")) {
	body = _p_add(wid, name, "value", "Dist:") + "<br>";	
	body += _p_add(wid, name, "signal", "Signal:") + "<br>";	
    }
    else if (wname.startsWith("Dispersy")) {
    body = _p_add(wid, name, "swift.state", "Swift") + "<br>"
    body += _p_add(wid, name, "swift.num_peers", "Peers") + "<br>"
    body += _p_add(wid, name, "swift.num_seeding", "Seeding") + "<br>"
    body += _p_add(wid, name, "swift.num_downloading", "Downloading") + "<br>"
    body += _p_add(wid, name, "swift.done_downloads", "Finished") + "<br>"
    body += _p_add(wid, name, "swift.up_speed", "Up speed", trim_float2) + "<br>"
    body += _p_add(wid, name, "swift.down_speed", "Down speed", trim_float2) + "<br>"
    body += _p_add(wid, name, "swift.raw_total_up", "Total up", trim_float2) + "<br>"
    body += _p_add(wid, name, "swift.raw_total_down", "Total down", trim_float2) + "<br>"
    }
    else {
	console.log("Unknown widget: " + wchannel + ":" + wname);
    }

    if (c == undefined)
	c = "medium";

    return get_base_widget(wchannel, wname, body, c, extra, log_module);
}

function reset() {
    op_clock = 0;
    refresh();
}



function toggleExpand(widget, size) {
    var id = "#" + widget;
    if (size == "small") {
	$(id + "_extra").hide(200);
	$(id + "_body").hide(200);
	$(id).addClass("small", 200).removeClass("big", 200).removeClass("medium", 200);
    } else if (size == "big") {
	console.log("Showing extra: " + id + "_extra");
	$(id + "_extra").show(200);
	$(id + "_body").show(200);
	$(id).addClass("big", 200).removeClass("small", 200).removeClass("medium", 200);
    } else {
	$(id).addClass("medium", 200).removeClass("small", 200).removeClass("big", 200);
	$(id + "_extra").hide(200);
	$(id + "_body").show(200);
    }
}


function splitChannel(channel) {
    var pos = channel.lastIndexOf(".");
    if (pos >= 0) {
	var bit1 = channel.substring(0, pos);
	var bit2 = channel.substring(pos+1);
    } else {
	var bit1 = "";
	var bit2 = channel;
    }
    return [bit1, bit2];
}

function is_updated() {
    if (session == 0) {
	return;
    }

    // Don't update if we're not running and we got the image already
    if (last_camera_update != get_time()) {
	for (var i in cameras) {
	    update_camera(cameras[i]);
	}
	last_camera_update = get_time();
    }

    var req = new XMLHttpRequest();
    req.onreadystatechange = function() {
	if ((req.readyState == 4) && (req.status == 200)) {
	    var data = null;
	    try {
		console.log(req.responseText);
		data = JSON.parse(req.responseText);
	    } catch (e) {
		alert("Bad dataset from server (" + e + "):"  + req.responseText);
		return;
	    }
	    if (data.op_clock !== op_clock) {
 		update_widgets();
		if (data.op_clock == 0) {
		    console.log("Jikes - got 0 opclock back")
		} else {
		    op_clock = data.op_clock;
		}
	    }
	    document.getElementById("server_time").innerHTML = new Date(data.server_time * 1000) + "(" + op_clock + ")";
	}
    }
    var now = get_time();
    req.open("GET", "/state?session="+session + "&ts=" + now + "&since="+op_clock);
    req.send(null);
    //document.getElementById("server_time").innerHTML = new Date(now * 1000) + "(" + op_clock + ")";
}


function update_camera(camera) {
    // camera is {widget, instrumentid}
    var req = new XMLHttpRequest(); 
    req.onreadystatechange = function() {
	if ((req.readyState == 4) && (req.status == 200)) {
	    // Update the widget with the correct url
	    data = JSON.parse(req.responseText);
	    // Data contains 'img' = id
	    if (camera.q) 
		var new_url = "/pic?img="+ data.img + "&q=" + camera.q;
	    else
		var new_url = "/pic?img="+ data.img + "&q=0";
	    if ($("#" + camera.widget + "_pic").attr("src") == new_url) return;

	    console.log("Updating image url: " + new_url);
	    $("#" + camera.widget + "_pic").attr("src", new_url);
	    $("#" + camera.widget + "_ref").attr("href", "/pic?img=" + data.img + "&q=0.4");

	    // Also do histogram
	}
    }
    req.open("GET", "/pic?t="+get_time() + "&instrumentid=" + camera.instrumentid);
    req.send(null);
}

function refresh() {
    update_widgets(true);
}

function new_session() {
    var req = new XMLHttpRequest(); 
    req.open("GET", "/newsession/", false);
    req.send(null);
    data = JSON.parse(req.responseText);
    session = data["sessionid"];
}

function add_param(widget_id, channel, param) {
    var req = new XMLHttpRequest(); 
    req.open("GET", "/add_param/"+channel+"/"+param + "?session="+session + "&data=" + widget_id);
    req.send(null); 
}	 

function use_session(session_id, on_completed_cb) {
    var reset = false;
    if (session_id !== session) 
	reset = true;
    session = session_id;

    // Get info about this view
    var req = new XMLHttpRequest();
    req.onreadystatechange = function() {
	if ((req.readyState == 4) && (req.status == 200)) {
	    var data = null;
	    try {
		data = JSON.parse(req.responseText);
	    } catch (e) {
		alert("Bad dataset from server (" + e + "):"  + req.responseText);
		return;
	    }
	    // Update the view info
	    varid_to_name = data.view.var_map;
	    varname_to_id = {}
	    for (varid in varid_to_name) {
		var full_name = varid_to_name[varid][0] + "." + varid_to_name[varid][1];
		varname_to_id[full_name] = varid;
	    }

	    // var_to_widget is based on full_name -> widget id
	    id_to_widget = {};
	    for (var pid in data.view.data) {
		var widget_id = data.view.data[pid];
		id_to_widget[pid] = widget_id;
                // If we want to load saved views, this is where we'd do it
	    }
	    
            update_widgets(true);
	    
	    for (var b in buttons) {
		$(function() { $("#"+ b).button()});
		// Change the button state based on the config param
		get_config(buttons[b], function(s) {console.log("#"+b + "=" + s);  $("#"+b).attr("checked",s); $("#"+b).button("refresh")});
	    }
	    if (on_completed_cb)
		on_completed_cb.call();
	}
    }
    req.open("GET", "/list_view?session="+session, false);
    req.send(null);
}

function get_var_fullname(var_id) {
    return varid_to_name[var_id][0] + "." +  varid_to_name[var_id][1];
}

function get_var_name(var_id) {
    return varid_to_name[var_id];
}

function update_widgets(full) {

    var req = new XMLHttpRequest(); 
    req.onreadystatechange = function() {
     	if ((req.readyState == 4) && (req.status == 200)) {

	    try {
		dataset = JSON.parse(req.responseText);
	    } catch (e) {
		alert("Bad dataset from server (" + e + "):"  + req.responseText);
		return;
	    }
	    _request_still_open = false;

	    // We split the dataset into the various widgets
	    for (var j in dataset) {
		var entries = dataset[j];
		if (entries.length == 4) {
		    var name = get_var_name(entries[2]);
		    if (name == undefined) {
			console.log("Got unknown var: " + entries[2]);
			continue;
		    }
		    var entry = {"id": entries[2],
				 "channel": name[0],
				 "name": name[1],
				 "value": entries[3],
				 "full_name": get_var_fullname(entries[2]),
				 "style": "d" + j%2,
	                         "widget": id_to_widget[entries[2]],
				 "convert": widget_to_convert[id_to_widget[entries[2]]]};
		    // Update this widget
		    update_state(entry);
		}
	    }
	}
    }

    var now = get_time();
    if (full == true) 
	req.open("GET", "/fullstate?session=" + session + "&ts=" + now);
    else {
	if (_request_still_open) return;
	_request_still_open = true;
	//	console.log("Requesting updates since op_clock " + op_clock);
	req.open("GET", "/get_changes/" + (op_clock-100) + "?session=" + session +"&st=" + last_time + "&ts=" + now);
    }
    last_time = now;
    req.send(null);
}

function update_alarm(widget, param, element, value, state) {
    var l = alarms[widget][param];
    for (var i=0; i<l.length; i++) {
	if (l[i][2] == state) {
	    if (value == "") { // Delete the whole thing
		console.log("Deleting");
		l.splice(i, 1);
		return;
	    }
	    l[i][element] = value;
	    return; 
	}
    }
    if (value == "") return;

    // Didn't have this one, add it
    var min = 0; 
    var max = 0;
    var eq = undefined;
    if (element == 0) min = value;
    if (element == 1) max = value;
    if (element == 3) eq = value;
    l.push([min, max, state, eq]);
}

function show_alarms(widget, elem) {
   html = "";
    if (alarms[widget] == undefined) {
	alarms[widget] = {};
    }
    if (alarms[widget][elem] == undefined) {
	alarms[widget][elem] = [];
    }
   for (var id in alarms[widget]) {
     var l = alarms[widget][id];
     if (elem == undefined || elem == id) {
       html += "<h3>" + id + "</h3>";
       var bad = false;
       var ugly = false;
       for (var j=0; j< l.length; j++) {
         if (l[j][2] == BAD) bad = true;
         if (l[j][2] == UGLY) ugly = true;
	   var eq = "";
	   if (l[j][3] != undefined) eq = l[j][3];
         html += "<b>" + state[l[j][2]] + "</b>: min: <input size=7 onchange=\"update_alarm('"+widget+"', '"+id+"', '0', this.value, '" + l[j][2] + "')\" value=\"" + l[j][0] + "\">";
	 html += " max: <input size=7 onchange=\"update_alarm('"+widget+"', '"+id+"', '1', this.value, '" + l[j][2] + "')\" value=\"" + l[j][1] + "\">";
	 html += " eq: <input size=7 onchange=\"update_alarm('"+widget+"', '"+id+"', '3', this.value, '" + l[j][2] + "')\" value=\"" + eq + "\"><br>";
       }
       // Also add a new line?
       if (!bad) {
         html += "<b>bad</b> min: <input size=7 onchange=\"update_alarm('"+widget+"', '"+id+"', '0', this.value, "+ BAD + ")\" value=\"\">";
         html += " max: <input size=7 onchange=\"update_alarm('"+widget+"', '"+id+"', '1', this.value, "+BAD+")\" value=\"\">";
	 html += " eq: <input size=7 onchange=\"update_alarm('"+widget+"', '"+id+"', '3', this.value, '" + BAD + "')\" value=\"\"><br>";
       }
       if (!ugly) {
         html += "<b>ugly</b> min: <input size=7 onchange=\"update_alarm('"+widget+"', '"+id+"', '0', this.value, "+ UGLY + ")\" value=\"\">";
         html += " max: <input size=7 onchange=\"update_alarm('"+widget+"', '"+id+"', '1', this.value, "+UGLY+")\" value=\"\">";
	 html += " eq: <input size=7 onchange=\"update_alarm('"+widget+"', '"+id+"', '3', this.value, '" + UGLY + "')\" value=\"\"><br>";
       }
     }
   } 
   $("#alarms").html(html);
   //$("#alarms").show(200);
    console.log("Showing alarm: " + html);
   $("#alarms").dialog({width:700, height:300, modal:true, buttons: {Ok: function() {$(this).dialog("close")}}});
}

function get_state_equals(id, initial_state, target_value, target_state) {
    if ( $("#" + id).html() === ""+target_value) {
	return target_state;
    }
    return initial_state;
}    

function get_state_float(id, initial_state, min_value, max_value, target_state) {
    //    console.log(id + "," + initial_state + "," + min_value + "," + max_value + "," + target_state + "," + parseFloat($("#" + id).html()));
   var c = initial_state;
   var val = parseFloat($("#" + id).html());
   if (val <= max_value && val >= min_value) {
      c = Math.max(c, target_state);
      // Color the parameter too
   }
   return c;
}

function monitor_state() {

   var worst_state = GOOD;

   // Periodically monitor and update states for custom widgets
   // Power widget
   for (widget in alarms) {
    var widget_state = GOOD;
    for (var id in alarms[widget]) {
    l = alarms[widget][id];
    var c = GOOD;
    for (var i=0; i<l.length; i++) {
	if (l[i][3] != undefined) 
	    c = get_state_equals(id, c, l[i][3], l[i][2]);
	else
	    c = get_state_float(id, c, l[i][0], l[i][1], l[i][2]);
    }
    worst_state = Math.max(worst_state, c);
    widget_state = Math.max(widget_state, c);
    $("#" + id).removeClass("ok").removeClass("error").removeClass("warning").addClass(text_state[c]);
   }
    // Update header			     
    $("#" + widget + "_s").removeClass("good").removeClass("bad").removeClass("ugly").addClass(state[widget_state]);
   }

   if (worst_state == BAD) {
    sound_alarm(true);
   } else {
    sound_alarm(false);
   }
}


function get_state() {
    var l = [];
    $("#sortable li").each( function() {
	var classes = $("#" + this.id).attr("class");
	if (classes.search("big") > -1)
            l.push([this.id, "big"])
	else if (classes.search("medium") > -1)
	    l.push([this.id, "medium"])
	else
	    l.push([this.id, "small"])
    });

    return l;
}