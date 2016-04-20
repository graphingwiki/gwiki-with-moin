define([
    "collabcommon/common/Dict",
    "collabcommon/common/EventSource",
    "collabcommon/common/Strophe"
], function(Dict, EventSource) {
    "use strict";

    var getRoomJid = function(roomName, baseJid) {
        var node = Strophe.getNodeFromJid(roomName);
        if (node !== null) {
            return roomName;
        }
        var domain = Strophe.getDomainFromJid(baseJid);
        return roomName + "@conference." + domain;
    };

    var iterChildren = function(element, func, context) {
        var children = element.childNodes;

        for (var i = 0, child = null; child = children[i]; i++) {
            if (func.call(context, child, i) === false) break;
        }
    };


    var now = Date.now || function() {
        return (new Date()).getTime();
    };

    var rex = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.?(\d*)Z$/;

    var parseDelay = function(stanza) {
        var timestamp = null;

        iterChildren(stanza, function(child) {
            if (!child.tagName) return;
            if (child.tagName.toLowerCase() !== "delay") return;
            if (child.getAttribute("xmlns") !== "urn:xmpp:delay") return;

            var stamp = child.getAttribute("stamp");
            if (stamp === null) return;

            var newStamp = stamp.match(rex);
            if (newStamp === null) return;

            var fraction = newStamp.pop();

            newStamp.shift();
            newStamp[1] -= 1;
            timestamp = Date.UTC.apply(null, newStamp);

            if (fraction) {
                timestamp += 1000 * Number("0." + fraction);
            }
        });

        return timestamp === null ? now() : timestamp;
    };

    var onUnload = function(fn) {
        var events = ["beforeunload", "unload"];
        var callback = function() {
            events.forEach(function(event) {
                window.removeEventListener(event, callback)
            });
            fn();
        };

        events.forEach(function(event) {
            window.addEventListener(event, callback);
        });
    };

    var Connection = function(boshUri, roomJid, jid, password) {

        this.roomJid = getRoomJid(roomJid, jid);
        this.jid = jid;
        this.password = password;

        this.strophe = new Strophe.Connection(boshUri);
        this.strophe.connect(jid, password, this._statusChanged.bind(this));

        this.participants = new Dict();

        this.queue = [];
        this.timeout = null;

        onUnload(function() {
            this.strophe.disconnect();
        }.bind(this));


    };

    Connection.prototype = new EventSource(this);

    Connection.prototype._addToQueue = function(timestamp, sender, text) {
        if (this.timeout === null) {
            this.timeout = setTimeout(this._flushQueue.bind(this), 0);
        }
        this.queue.push({
            timestamp: timestamp,
            sender: sender,
            text: text
        });
    };

    Connection.prototype._flushQueue = function() {
        this.timeout = null;
        this.queue.sort(function(x, y) {
            return x.timestamp - y.timestamp;
        });

        for (var i = 0, len = this.queue.length; i < len; i++) {
            var obj = this.queue[i];
            var isSelf = this.resource === obj.sender || Strophe.getNodeFromJid(this.jid) === obj.sender;
            this.trigger("message", obj.timestamp, obj.sender, obj.text, isSelf);
        }
        this.queue = [];
    };

    Connection.prototype.send = function(message) {
        var msg = $msg({
            to: this.roomJid,
            type: "groupchat"
        });

        msg.c("body").t(message);
        this.strophe.send(msg.tree());
    };

    Connection.prototype._connected = function() {
        this.strophe.addHandler(this._handleMessage.bind(this),
            null, "message", null, null,
            this.roomJid, { matchBare: true });

        this.strophe.addHandler(this._handlePresence.bind(this),
            null, "presence", null, null,
            this.roomJid, { matchBare: true });

        var resource = Strophe.getNodeFromJid(this.jid);
        var id = ((999 * Math.random()) | 0);

        var storage = window.sessionStorage;
        if (storage){
            if (storage.getItem("webchatid")){
                id = storage.getItem("webchatid");
            }else{
                storage.setItem("webchatid", id);
            }
        }

        resource = resource + "-" + id;

        var presence = $pres({
            to: this.roomJid + "/" + resource
        });
        presence.c("x", {
            xmlns: "http://jabber.org/protocol/muc"
        });
        this.strophe.send(presence);

        this.trigger("connected");
    };

    Connection.prototype._disconnected = function() {
        this.trigger("disconnected");
    };

    Connection.prototype._handleMessage = function(msg) {
        var from = msg.getAttribute("from");
        var sender = Strophe.getResourceFromJid(from);

        iterChildren(msg, function(child) {
            if (child.tagName && child.tagName.toLowerCase() === "body") {
                var timestamp = parseDelay(msg);
                this._addToQueue(timestamp, sender, child.textContent);
                return false;
            }
        }, this);

        return true;
    };

    Connection.prototype._handlePresence = function(pres) {
        var type = pres.getAttribute("type");

        var from = pres.getAttribute("from");
        var sender = Strophe.getResourceFromJid(from);

        if (type !== "unavailable" && this.participants.contains(from)) {
            return true;
        }

        var msg = "";
        if (type === "unavailable") {
            msg = "has left the room";
            this.participants.pop(from);
            this.trigger("participantLeave", sender);
        } else {
            msg = "has entered the room";
            this.participants.set(from, true);
            this.trigger("participantJoin", sender, true);
        }
        this.trigger("message", now(), null, sender + " " + msg);

        return true;
    };

    Connection.prototype._setStatus = function(isError, status) {
        this.status = status;
        this.trigger("statusChanged", isError, status);
    };

    Connection.prototype._statusChanged = function(status) {
        if (status == Strophe.Status.CONNECTING) {
            this._setStatus(false, "Connecting");
        } else if (status == Strophe.Status.CONNFAIL) {
            this._setStatus(true, "Connection failed");
            this.strophe.disconnect();
        } else if (status == Strophe.Status.AUTHENTICATING) {
            this._setStatus(false, "Authenticating");
        } else if (status == Strophe.Status.AUTHFAIL) {
            this._setStatus(true, "Authentication failed");
            this.strophe.disconnect();
        } else if (status == Strophe.Status.DISCONNECTING) {
            this._setStatus(false, "Disconnecting");
        } else if (status == Strophe.Status.DISCONNECTED) {
            this._setStatus(false, "Disconnected");
            this._disconnected();
        } else if (status == Strophe.Status.CONNECTED) {
            this._setStatus(false, "Connected");
            this._connected();
        }
    };

    return Connection;
});
