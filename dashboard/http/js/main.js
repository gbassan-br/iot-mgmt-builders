var led = "";
var alexa = "";
var mymap = "";
var markers = {};
var choicesDevice = {};

//Retrieve the template data from the HTML (jQuery is used here).
var info = $('#deviceInfo').html();
var shadow = $('#deviceLed').html();
var alex = $('#deviceAlexa').html();


// Compile the template data into a function
var infoScript = Handlebars.compile(info);
var shadowLedScript = Handlebars.compile(shadow);
var shadowAlexaScript = Handlebars.compile(alex);

//function to get string parameters
function GetQueryStringParams(sParam){
      var sPageURL = window.location.search.substring(1);
	    var sURLVariables = sPageURL.split('&');
      for (var i = 0; i < sURLVariables.length; i++)
      {
        var sParameterName = sURLVariables[i].split('=');
	      if (sParameterName[0] == sParam){
          return sParameterName[1];
          }
        else{
          //if something wrong with querystring, returning all string
          console.log("No querystring or no location parameter, returning all");
          return "all";
        }
        }
      };
  /**
  * utilities to do sigv4
  * @class SigV4Utils
  */
 function SigV4Utils() { }

 // generate signature key for sigv4 request
 SigV4Utils.prototype.getSignatureKey = function (key, date, region, service) {
     var kDate = AWS.util.crypto.hmac('AWS4' + key, date, 'buffer');
     var kRegion = AWS.util.crypto.hmac(kDate, region, 'buffer');
     var kService = AWS.util.crypto.hmac(kRegion, service, 'buffer');
     var kCredentials = AWS.util.crypto.hmac(kService, 'aws4_request', 'buffer');
     return kCredentials;
 };
 
 // create signed URL using sigv4 to call wss ioot
 SigV4Utils.prototype.getSignedUrl = function (host, region, credentials) {
     var datetime = AWS.util.date.iso8601(new Date()).replace(/[:\-]|\.\d{3}/g, '');
     var date = datetime.substr(0, 8);
 
     var method = 'GET';
     var protocol = 'wss';
     var uri = '/mqtt';
     var service = 'iotdevicegateway';
     var algorithm = 'AWS4-HMAC-SHA256';
 
     var credentialScope = date + '/' + region + '/' + service + '/' + 'aws4_request';
     var canonicalQuerystring = 'X-Amz-Algorithm=' + algorithm;
     canonicalQuerystring += '&X-Amz-Credential=' + encodeURIComponent(credentials.accessKeyId + '/' + credentialScope);
     canonicalQuerystring += '&X-Amz-Date=' + datetime;
     canonicalQuerystring += '&X-Amz-SignedHeaders=host';
 
     var canonicalHeaders = 'host:' + host + '\n';
     var payloadHash = AWS.util.crypto.sha256('', 'hex')
     var canonicalRequest = method + '\n' + uri + '\n' + canonicalQuerystring + '\n' + canonicalHeaders + '\nhost\n' + payloadHash;
 
     var stringToSign = algorithm + '\n' + datetime + '\n' + credentialScope + '\n' + AWS.util.crypto.sha256(canonicalRequest, 'hex');
     var sigv4 = new SigV4Utils();
     var signingKey = sigv4.getSignatureKey(credentials.secretAccessKey, date, region, service);
     var signature = AWS.util.crypto.hmac(signingKey, stringToSign, 'hex');
 
     canonicalQuerystring += '&X-Amz-Signature=' + signature;
     if (credentials.sessionToken) {
         canonicalQuerystring += '&X-Amz-Security-Token=' + encodeURIComponent(credentials.sessionToken);
     }
 
     var requestUrl = protocol + '://' + host + uri + '?' + canonicalQuerystring;
     return requestUrl;
 };
 

 // creating wss Paho client to connect to iot
 function WSClient(clientId,host,region,credentials,messageReceivedCallback) {
    var sigv4 = new SigV4Utils();
    var requestURL = sigv4.getSignedUrl(host, region, credentials);
    this.client = new Paho.MQTT.Client(requestURL, clientId);
    var self = this;
    this.messageCallback = messageReceivedCallback;
    var connectOptions = {
        onSuccess: function () {
            console.log('IoT Connected with success');
            // subscribing the device topics to render the panels
            //sensor data
            self.client.subscribe("devices/temperature/+/#");
            //listen on shadow reported
            self.client.subscribe("$aws/things/+/shadow/get/accepted")
            //listen on shadow deltas
            self.client.subscribe("$aws/things/+/shadow/update/accepted")
        },
        useSSL: true,
        timeout: 3,
        mqttVersion: 4,
        onFailure: function () {
            console.log('failure');
        }
    };
    this.client.connect(connectOptions);
    this.client.onMessageArrived = WSClient.prototype.onMessageArrived.bind(this);
}

// callback to any mqtt message that arrives
WSClient.prototype.onMessageArrived = function(message) {

    // getting the incomming topic
    var topic = message.topic
    //console.log(topic);
    //parsing mqtt json message
    var payload = JSON.parse(message.payloadString)
    //console.log(payload);
    //shadow processing routing - both reported and deltas
    if(topic.includes("shadow/get")){

      //getting deviceID from topic name - as is default $aws topic
      var deviceID = topic.substring(topic.indexOf("things/")+7,topic.indexOf("/shadow"));
      
      // getting led reported state to create <img/> component and push it to handlebars
      var led = "img/led_"+payload.state.reported.ledcolor+".png";

      var context = {
        'led': led,
      };
      //creting the template binding and pushing vi jQuery
      //dynamcaly setting the jquery DOM to specific device
      var html = shadowLedScript(context);
      $("#"+deviceID+"_led").html(html);

      if(payload.state.reported.rogue){
        //getting deviceID from topic name - as is default $aws topic
        var deviceID = topic.substring(topic.indexOf("things/")+7,topic.indexOf("/shadow"));
        
        //changing rogue panel color
        $("#"+deviceID+"_panel").css("background-color","rgba(255, 0, 0, 0.45)");
        $("#"+deviceID+"_check").prop('checked', true);
        var resonText;
        var reasonCode;
        switch(payload.state.reported.reason){
          case "aws:num-messages-sent":
            reasonCode=1;
            resonText="Extra message";
            break;
          case "aws:message-byte-size":
            reasonCode=2;
            resonText="Large message";
            break;
          case "aws:num-authorization-failures": 
            reasonCode=3;
            resonText="Invalid topic";
            break;
        }
        $("#dropdown_"+deviceID).show();
        $("#btn_"+deviceID).html(resonText);
        $("#btn_"+deviceID).val(reasonCode);
      }else{
        if(lab3){
          $("#"+deviceID+"_panel").css("background-color","#FFFFFF");
        }
      }

      if(payload.state.reported.powersave!=null){
        var deviceID = topic.substring(topic.indexOf("things/")+7,topic.indexOf("/shadow"));
        if(payload.state.reported.powersave=="powersave"){
          $("#"+deviceID+"_panel").css("background-color","rgba(255, 0, 0, 0.45)");
        }else{
          $("#"+deviceID+"_panel").css("background-color","#FFFFFF");
        }
      }

      //getting deviceID from topic name - as is default $aws topic
      var deviceID = topic.substring(topic.indexOf("things/")+7,topic.indexOf("/shadow"));
      
      // getting led reported state to create <img/> component and push it to handlebars
      var  alexa = "img/"+payload.state.reported.alexastatus+".png";

      var context = {
        'alexa': alexa,
      };
      //creting the template binding and pushing vi jQuery
      //dynamcaly setting the jquery DOM to specific device
      var html = shadowAlexaScript(context);
      $("#"+deviceID+"_alexa").html(html);

    }else if(topic.includes("shadow/update")){
      //getting deviceID from topic name - as is default $aws topic
      if(payload.state.reported.powersave!=null){
        var deviceID = topic.substring(topic.indexOf("things/")+7,topic.indexOf("/shadow"));
        if(payload.state.reported.powersave=="powersave"){
          $("#"+deviceID+"_panel").css("background-color","rgba(255, 0, 0, 0.45)");
        }else{
          $("#"+deviceID+"_panel").css("background-color","#FFFFFF");
        }
      }
      if(payload.state.reported.alexastatus!=null){
        var deviceID = topic.substring(topic.indexOf("things/")+7,topic.indexOf("/shadow"));
        // getting led reported state to create <img/> component and push it to handlebars
        var  alexa = "img/"+payload.state.reported.alexastatus+".png";

        var context = {
          'alexa': alexa,
        };
        //creting the template binding and pushing vi jQuery
        //dynamcaly setting the jquery DOM to specific device
        var html = shadowAlexaScript(context);
        $("#"+deviceID+"_alexa").html(html);
      }
      if(payload.state.reported.ledcolor!=null){
        //getting deviceID from topic name - as is default $aws topic
        var deviceID = topic.substring(topic.indexOf("things/")+7,topic.indexOf("/shadow"));
        
        // getting led reported state to create <img/> component and push it to handlebars
        var led = "img/led_"+payload.state.reported.ledcolor+".png";

        var context = {
          'led': led,
        };
        //creting the template binding and pushing vi jQuery
        //dynamcaly setting the jquery DOM to specific device
        var html = shadowLedScript(context);
        $("#"+deviceID+"_led").html(html);
      }
      if(payload.state.reported.rogue && lab3){
        //getting deviceID from topic name - as is default $aws topic
        var deviceID = topic.substring(topic.indexOf("things/")+7,topic.indexOf("/shadow"));
        //changing rogue panel color
        $("#"+deviceID+"_panel").css("background-color","rgba(255, 0, 0, 0.45)");
        $("#"+deviceID+"_check").prop('checked', true);
        var resonText;
        var reasonCode;
        switch(payload.state.reported.reason){
          case "aws:num-messages-sent":
            reasonCode=1;
            resonText="Extra message";
            break;
          case "aws:message-byte-size":
            reasonCode=2;
            resonText="Large message";
            break;
          case "aws:num-authorization-failures": 
            reasonCode=3;
            resonText="Invalid topic";
            break;
        }
        $("#dropdown_"+deviceID).show();
        $("#btn_"+deviceID).show();
        $("#btn_"+deviceID).html(resonText);
        $("#btn_"+deviceID).val(reasonCode);
      }
    }else{
      //getting device info from topic message
      deviceID = payload.deviceID;
      region = payload.location;
      if(payload.temp_unit=="celsius"){
        tempunit = "C"
      }else{
        tempunit = "F"
      };
      //sending  shadow get message to get last shadow status
      message = new Paho.MQTT.Message("");
      message.destinationName = "$aws/things/"+deviceID+"/shadow/get";
      self.client.send(message)


      //setting device info via handlebars
      var context = {
        'deviceId': payload.deviceID,
        'region':payload.location
      };
      //creting the template binding and pushing vi jQuery
      //dynamcaly setting the jquery DOM to specific device
      $("#"+deviceID+"_temp").gaugeMeter({percent:Math.round(payload.temp)});
      $("#"+deviceID+"_humid").gaugeMeter({percent:payload.humid});
      var html = infoScript(context);
      $("#"+deviceID+"_info").html(html);

    }
    
  
    
    if (this.messageCallback) this.messageCallback(message.payloadString);
};

WSClient.prototype.disconnect = function() {
    this.client.disconnect();
}

//function to get all unique locations
function onlyUnique(value, index, self) { 
  return self.indexOf(value) === index;
}

//function to render the device panels
//could be filtered by region
function createDevices(region){
  var viewLong = 0;
  var viewLat = 0;
  var zoom = 0;
  var mapbox = "";
  switch(region){
    case "SaoPaulo":
      viewLong = -23.543845;
      viewLat = -46.63765;
      zoom = 11;
      mapbox = "mapbox.streets";
      break;
      case "LasVegas":
      viewLong = 36.156727;
      viewLat = -115.187531;
      zoom = 11;
      mapbox = "mapbox.streets";
      break;
      case "Miami":
      viewLong = 25.86602;
      viewLat = -80.259933;
      zoom = 11;
      mapbox = "mapbox.streets";
      break;
      case "NYC":
      viewLong = 40.881852;
      viewLat = -73.929062;
      zoom = 11;
      mapbox = "mapbox.streets";
      break;
      case "SanFrancisco":
      viewLong = 37.7433;
      viewLat = -122.43782;
      zoom = 11;
      mapbox = "mapbox.streets";
      break;                        
    default:
      viewLong = 20.303418;
      viewLat = -59.414063;
      zoom = 2;
      mapbox = "mapbox.satellite";
  };

  //setting map rendering according to region selected
  mymap = L.map('mapid').setView([viewLong, viewLat ], zoom);
  L.tileLayer('https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token=pk.eyJ1IjoiZ2Jhc3NhbiIsImEiOiJjam9idTd2dGoyNjJsM3BwYnpjZTh5MGd1In0.wFq1LzouEVaEi2_RarmDDA', {
    maxZoom: 18,
    attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors, ' +
      '<a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, ' +
      'Imagery © <a href="https://www.mapbox.com/">Mapbox</a>',
    id: mapbox
  }).addTo(mymap);
  mymap.scrollWheelZoom.disable()


  // function onMapClick(e) {
  //   alert("You clicked the map at " + e.latlng);
  // }

  // mymap.on('click', onMapClick);


  //creating dynamo client
  var dynamodb = new AWS.DynamoDB();

  //dynamodb device table
  var params = {
    ExpressionAttributeNames: {
      '#lg': 'long',
      '#lt': 'lat'
    },
    ProjectionExpression: "deviceID, attributes, #lg, #lt",  
    TableName: "devices-simulator"
   };

   //scan the table to see which devices must be rendered
   dynamodb.scan(params, function(err, data) {
     if (err){
        console.log(err, err.stack);
      } // an error occurred
     else{
       console.log("Dynamo Scanned Successfuly");
       // successful response
       var devices = data.Items;
       var frag = document.createDocumentFragment();
       
      //getting unique locations to build the header
       var locations = [];
       $.each( devices, function( i, device ) {
          locations.push(device.attributes.M.Location.S);
       });
       //getting unique locations to sort and organize the dashboard
       var locationUnique = locations.filter( onlyUnique );
       //sort alphabetically
       locationUnique.sort();

       //sorting the devices by serialnumber
       devices.sort(function(a,b){
         return a.attributes.M.serialNumber.S - b.attributes.M.serialNumber.S;
       });

       //jQuery forEach loop to create html divs
       $.each(locationUnique, function(i, location){

        //filter out by region
        //TO-DO implement filter header or other mechanism like maps
        if(location==region||region=="all"){
          var regionColumn = document.createElement("div");
          regionColumn.className = "col-md-12";
          var header = document.createElement("h3");
          var regionName = document.createTextNode("Location: "+location);
          header.appendChild(regionName);
          regionColumn.appendChild(header);
          frag.appendChild( regionColumn );

          
          $.each( devices, function( i, device ) {
            deviceID = device.deviceID.S
            deviceRegion = device.attributes.M.Location.S;
            if(deviceRegion==location){


              //creating column 
              var deviceColumn = document.createElement("div");
              deviceColumn.className = "col-sm-2 col-md-2";
              
              //creating panel to organize info
              var devicePanel = document.createElement("div");
              devicePanel.className = "panel panel-default panel-style";
              devicePanel.setAttribute("id",deviceID+"_panel");

              
              //device information from sensor topic
              var deviceInfo = document.createElement("div");
              deviceInfo.className="panel-body info";
              deviceInfo.setAttribute("id",deviceID+"_info");

              //div for gauges
              var deviceGauges = document.createElement("div");
              deviceGauges.className="graphs";
              deviceGauges.setAttribute("id",deviceID+"_gauges");
              
              //creating temp gauge
              var deviceTempGauge = document.createElement("div");
              deviceTempGauge.className="GaugeMeter gaugeMeter";
              deviceTempGauge.setAttribute("id",deviceID+"_temp");
              deviceTempGauge.setAttribute("data-style","Arch");
              deviceTempGauge.setAttribute("data-theme","Green-Gold-Red");
              deviceTempGauge.setAttribute("data-stripe","2");
              deviceTempGauge.setAttribute("data-width","9");
              deviceTempGauge.setAttribute("data-size","90");
              deviceTempGauge.setAttribute("data-append","°");
              deviceTempGauge.setAttribute("data-label","Temp");


              //creating humid gauge
              var deviceHumidGauge = document.createElement("div");
              deviceHumidGauge.className="GaugeMeter gaugeMeter";
              deviceHumidGauge.setAttribute("id",deviceID+"_humid");
              deviceHumidGauge.setAttribute("data-style","Arch");
              deviceHumidGauge.setAttribute("data-theme","LightBlue-DarkBlue");
              deviceHumidGauge.setAttribute("data-stripe","2");
              deviceHumidGauge.setAttribute("data-width","9");
              deviceHumidGauge.setAttribute("data-size","90");
              deviceHumidGauge.setAttribute("data-append","%");
              deviceHumidGauge.setAttribute("data-label","Humid");

              deviceGauges.appendChild(deviceTempGauge);
              deviceGauges.appendChild(deviceHumidGauge);

              //device information from sensor topic
              var deviceShadow = document.createElement("div");
              deviceShadow.className="panel-body icons";
              deviceShadow.setAttribute("id",deviceID+"_shadow");
          
              //device led status from shadow
              var deviceLed = document.createElement("div");
              deviceLed.className="div1";
              deviceLed.setAttribute("id",deviceID+"_led");

              //device temp bar chart - working progress
              var deviceAlexa = document.createElement("div");
              deviceAlexa.className="div2";
              deviceAlexa.setAttribute("id",deviceID+"_alexa"); 
              
              deviceShadow.appendChild(deviceLed);
              deviceShadow.appendChild(deviceAlexa);

              //device temp bar chart - working progress
              var deviceRogue = document.createElement("div");
              deviceRogue.className="panel-body rogue";
              deviceRogue.setAttribute("id",deviceID+"_rogue");
              
              //setting the checkbox to identify the rogue device
              var checkDiv = document.createElement("div");
              checkDiv.className="checkbox";

              var label = document.createElement("label");    
              var deviceCheck = document.createElement("input");
              deviceCheck.setAttribute("type", "checkbox");
              deviceCheck.setAttribute("id", deviceID+"_check");

              label.appendChild(deviceCheck);
              var text = document.createTextNode("Compromised?");
              label.appendChild(text);

              checkDiv.appendChild(label);

              dropDiv = document.createElement("div");
              dropDiv.className="dropdown rogue-btn";
              dropDiv.setAttribute("id","dropdown_"+deviceID);
              var dropBtn = document.createElement("button");
              dropBtn.setAttribute("type", "button");
              dropBtn.setAttribute("data-toggle", "dropdown");
              dropBtn.setAttribute("id","btn_"+deviceID);
              dropBtn.className="btn btn-primary dropdown-toggle";
              var textBtn = document.createTextNode("No problem");
              
              var ulist = document.createElement("ul");
              ulist.className="dropdown-menu dropdown-rogue";
              var l0 = document.createElement("li");
              var op0 = document.createElement("a");
              op0.setAttribute("href","#");
              var op0Text = document.createTextNode("No problem");
              op0.appendChild(op0Text);
              l0.appendChild(op0);
              
              var l1 = document.createElement("li");
              var op1 = document.createElement("a");
              op1.setAttribute("href","#");
              var op1Text = document.createTextNode("Extra messages");
              op1.appendChild(op1Text);
              l1.appendChild(op1);

              var l2 = document.createElement("li");
              var op2 = document.createElement("a");
              op2.setAttribute("href","#");
              var op2Text = document.createTextNode("Large message");
              op2.appendChild(op2Text);
              l2.appendChild(op2);

              var l3 = document.createElement("li");
              var op3 = document.createElement("a");
              op3.setAttribute("href","#");
              var op3Text = document.createTextNode("Invalid topic");
              op3.appendChild(op3Text);
              l3.appendChild(op3);

              ulist.appendChild(l0);
              ulist.appendChild(l1);
              ulist.appendChild(l2);
              ulist.appendChild(l3);
              dropDiv.appendChild(ulist);

              dropDiv.appendChild(ulist);
              dropBtn.appendChild(textBtn);
              dropDiv.appendChild(dropBtn);

              deviceRogue.appendChild(checkDiv);
              deviceRogue.appendChild(dropDiv);
          
              //adding everything in the main panel
              devicePanel.appendChild(deviceInfo);
              devicePanel.appendChild(deviceGauges);
              devicePanel.appendChild(deviceShadow);
              devicePanel.appendChild(deviceRogue);
              
              //adding everything on the column
              deviceColumn.appendChild(devicePanel)
              
              //creating fragment and loop

              frag.appendChild( deviceColumn );

              //adding just filtered devices on maps
              var marker = L.marker([device.long.S, device.lat.S]).addTo(mymap);
              marker.bindPopup("<b>"+deviceID+"</b><br><div id='"+deviceID+"_popup'class='panel'></div>");
              markers[deviceID] = marker;
            };
          });
        };
      });
      //adding devices fragment to the DOM via jQuery
      $("#devices")[0].appendChild( frag );
      $.each( devices, function( i, device ) {
        deviceID = device.deviceID.S
        deviceRegion = device.attributes.M.Location.S;
        //setting device info via handlebars
        var initialContext = {
          'deviceId': deviceID,
          'region':deviceRegion
        };
        //creting the template binding and pushing vi jQuery
        //dynamcaly setting the jquery DOM to specific device
        $("#"+deviceID+"_temp").gaugeMeter({percent:0});
        $("#"+deviceID+"_humid").gaugeMeter({percent:0});
        var html = infoScript(initialContext);
        $("#"+deviceID+"_info").html(html);
        var  alexa = "img/noalexa.png";

        var context = {
          'alexa': alexa,
        };
        //creting the template binding and pushing vi jQuery
        //dynamcaly setting the jquery DOM to specific device
        var html = shadowAlexaScript(context);
        $("#"+deviceID+"_alexa").html(html);
        // getting led reported state to create <img/> component and push it to handlebars
        var led = "img/led_white.png";

        var context = {
          'led': led,
        };
        //creting the template binding and pushing vi jQuery
        //dynamcaly setting the jquery DOM to specific device
        var html = shadowLedScript(context);
        $("#"+deviceID+"_led").html(html);
        //workaround to solve chrome problem on load and dynamic divs
        if(lab3){
          $('div.rogue').show();
        }
      });
     }
    });
    
}

//creating AWS credentials by cognito idpool using unauth
AWS.config.credentials = new AWS.CognitoIdentityCredentials({
  IdentityPoolId: IdentityPoolId,
});

//generating credentials and run the main routine
AWS.config.credentials.get(function(err) {
console.log("Cognito credentials get");
if (err) {
    console.log("ERROR SIGNING IN");
    console.log(err);
    return;
}
//initialize wss iot client
WSClient("dashboard",iotUrl,AWS.config.region,AWS.config.credentials);

//render devices
createDevices(GetQueryStringParams("location"));
});

// is this lab3?
$(window).on('load',function(){
  $(".GaugeMeter").gaugeMeter();
  if(lab3){
    $('.btn-danger').show();
  }
})


$('body').on('click', '.navbar-nav li a', function(event) {
  if(event.currentTarget.text=="List View"){
    $("#home").removeClass();
    $("#mapview").removeClass();
    $("#mapid").hide();
    $("#devices").show();
  }else if(event.currentTarget.text=="Map View"){
    $("#home").removeClass();
    $("#listview").removeClass();
    $("#mapid").show();
    $("#devices").hide();
    $("#mapid").css("height","700");
    mymap.invalidateSize(true);


  }else{
    $("#home").removeClass();
  }
});


// control clicked dropdown
$('body').on('click', '.dropdown-rogue li a', function (event){
  // working with compromissed buttons
  $(this).parents(".rogue-btn").find('.btn').html($(this).text());
  $(this).parents(".rogue-btn").find('.btn').val($(this).parents("li").index());
  if($(this).parents("li").index()==0){
    $(this).parents(".rogue-btn").parents(".rogue").find('input[type="checkbox"]').prop('checked', false);
  }else{
    $(this).parents(".rogue-btn").parents(".rogue").find('input[type="checkbox"]').prop('checked', true);
  }
  button = $(this).parents(".rogue-btn").parents(".rogue").attr("id");
  if(button!=undefined){
    if(button.includes("rogue")||button!=null){
      event.preventDefault();
    }
  }
});


var processSchema = function(data) {
  var promises = [];

  $.each(table, function() {
      var def = new $.Deferred();
      db.executeSql(sql, data, function(tx, results){
         def.resolve(results);
      });
      promises.push(def);
  });

  return $.when.apply(undefined, promises).promise();
}

//open devices popup
function markerFunction(deviceID){
  marker = markers[deviceID];
  markerCoord = marker._latlng;
  mymap.panTo(markerCoord)
  marker.openPopup();
};


//verify devices button action
$('#verify').on('click', function (event){

  //hiding all previous alerts
  $("#alert-sucess").hide();
  $("#alert-danger").hide();
  $("#alert-warning").hide();
  $("#alert-info").hide();
  var count = 0;
  var currentValue = 0;
  var alert;
  var i;
  var x;
  //initialize count by type array
  for (i = 1; i < 4; i++) {
    choicesDevice[i] = 0;
  }
  //creating dynamo client
  var dynamodb = new AWS.DynamoDB();
  event.preventDefault(); // To prevent following the link (optional)
  var $checkboxes = $('input[type="checkbox"]');
  var countCheckedCheckboxes = $checkboxes.filter(':checked');
  if(countCheckedCheckboxes.length>2){
    var promises = [];
    $.each( countCheckedCheckboxes, function( i, device ) {
      var def = new $.Deferred();
      var deviceID = device.id.substring(0, device.id.indexOf("_check"));
      var selectedBtn = $('#btn_'+deviceID).val();
      var params = {
        ExpressionAttributeValues: {
          ':d': {S: deviceID}
        },
        ExpressionAttributeNames: {
          '#t': 'type'
        },
        KeyConditionExpression: 'deviceID = :d',
        ProjectionExpression: 'deviceID, #t',
        TableName: 'devices-simulator'
      };
      dynamodb.query(params, (err, data)=> {
        if (err) {
          console.log("Error Querying device type");
        } else {
          if(data.Items[0].type.S==selectedBtn){
            //couting by type of compromised devices
            currentValue = choicesDevice[data.Items[0].type.S];
            choicesDevice[data.Items[0].type.S] = currentValue + 1;
            def.resolve(choicesDevice);
          }else{
            def.resolve(0);
          }
        }
      });
      promises.push(def);
    });
    $.when.apply($, promises).done(function() {

        // do something with the results
        if(choicesDevice['1']==3 && choicesDevice['2']==3 && choicesDevice['3']==3){
          $(".modal-header").attr("class","modal-header modal-header-success");
          $(".modal-header").html('<button type="button" class="close" data-dismiss="modal" aria-hidden="true">×</button>'
          +'<h4><i class="glyphicon glyphicon-ok-sign"></i> Success!</h4>');
          $(".modal-body").html('<strong>Congratulations!</strong> You have successfully identified all the compromised devices!<br><br>'
          +'Here are the devices you have identified correctly:<br><br><ul class="list-group">'
          +'<li class="list-group-item">'+choicesDevice['1']+' Extra messages devices </li>'
          +'<li class="list-group-item">'+choicesDevice['2']+' Large messages </li>'
          +'<li class="list-group-item">'+choicesDevice['3']+' Invalid topic</li></ul>');
          $('#verifyModal').modal("show");
        }else 
          if(choicesDevice['1']>=1 && choicesDevice['2']>=1 && choicesDevice['3']>=1){
            $(".modal-header").attr("class","modal-header modal-header-warning");
            $(".modal-header").html('<button type="button" class="close" data-dismiss="modal" aria-hidden="true">×</button>'
            +'<h4><i class="glyphicon glyphicon-exclamation-sign"></i> Warning!</h4>');
            $(".modal-body").html('<strong>Close enough!</strong> You have identified most of the compromised devices. Lets move forward! <br><br>'
            +'Here are the devices you have identified correctly:<br><br><ul class="list-group">'
            +'<li class="list-group-item">'+choicesDevice['1']+' Extra messages devices </li>'
            +'<li class="list-group-item">'+choicesDevice['2']+' Large messages devices </li>'
            +'<li class="list-group-item">'+choicesDevice['3']+' Invalid topic devices</li></ul>');
            $('#verifyModal').modal("show");
          }else{
            $(".modal-header").attr("class","modal-header modal-header-danger");
            $(".modal-header").html('<button type="button" class="close" data-dismiss="modal" aria-hidden="true">×</button>'
            +'<h4><i class="glyphicon glyphicon-remove-sign"></i> Error!</h4>');
            $(".modal-body").html('<strong>Nope!</strong> You have not identified all the compromised devices. Try again.<br><br>'
            +'Here are the devices you have identified correctly:<br><br><ul class="list-group">'
            +'<li class="list-group-item">'+choicesDevice['1']+' Extra messages devices </li>'
            +'<li class="list-group-item">'+choicesDevice['2']+' Large messages devices</li>'
            +'<li class="list-group-item">'+choicesDevice['3']+' Invalid topic devices</li></ul>');
            $('#verifyModal').modal("show");
          }
    }); 
    }else{
      $(".modal-header").html('<button type="button" class="close" data-dismiss="modal" aria-hidden="true">×</button>'
      +'<h4><i class="glyphicon glyphicon-info-sign"></i> Information</h4>');
      $(".modal-body").html('<strong>Sorry!</strong> You have not selected all the compromised devices. Try again.');
      $(".modal-header").attr("class","modal-header modal-header-info");
      $('#verifyModal').modal("show");
  }
});


