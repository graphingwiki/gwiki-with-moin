/*
 MetaTable.js
 - js improvements for MetaTable
 License:	MIT <http://www.opensource.org/licenses/mit-license.php>
 Copyright: 2011 by Lauri Pokka
 Depends: MooTools HtmlTable.sort InlineEditor Request.SetMetas Events.shiftclick More/Date
 */

(function() {
    var preformatTable = function(tab) {
        var head = tab.getElement('thead');
        if (!head) {
            head = new Element('thead').inject(tab, 'top');
            if (!head.getElement('tr')) {
                head.grab(tab.getElement('tr'));
            }
        }

        head.getElements('td')
            .addClass('head_cell')
            .setStyle('white-space', 'nowrap');

        return tab;
    };

    var diff = function(o1, o2) {
        var changed = [];
        Object.each(o2, function(metas, page) {
            if (!o1[page]) changed.include(page);
            else {
                Object.each(metas, function(values, key) {
                    var values2 = o1[page][key];
                    if (!values2 ||
                        !values.every(values2.contains.bind(values2)) ||
                        !values2.every(values.contains.bind(values)))
                        changed.include(page);
                });
            }
        });
        return changed;

    };

    var HideableTable = new Class({
        Extends: HtmlTable,

        initialize: function(){
            this.parent.apply(this, arguments);

            this.hiddenCells = [];
        },

        enableHiding: function() {
            this.disableHiding();
            this.head.getElements('td, th').each(function(td) {
                var style = {
                    //'float': 'right',
                    'color': 'green',
                    'cursor': 'pointer',
                    'margin-left' : '4px',
                    'margin-right': 0
                };

                td.getElement('div').grab(new Element('a', {
                    'html': '&#171;',
                    'class' : 'hidelink',
                    'title': 'hide column',
                    'styles': style
                })).setStyle('white-space', 'nowrap');
                td.grab(new Element('a', {
                    'html': '&#187;',
                    'class' : 'showlink',
                    'title': 'show column',
                    'styles': style
                }).setStyle('display', 'none'));

                return this;
            });

            this.head.addEvents({
                'click:relay(a.hidelink)': function(event) {
                    this.hide.apply(this, [this.head.getElements('a.hidelink').indexOf(event.target)]);
                }.bind(this),
                'click:relay(a.showlink)': function(event) {
                    this.show.apply(this, [this.head.getElements('a.showlink').indexOf(event.target)]);
                }.bind(this)
            });

            return this;
        },

        disableHiding: function() {
            this.head.getElements('a.hidelink, a.showlink').destroy();
            this.head.removeEvents('click:relay(a.hidelink)');
            this.head.removeEvents('click:relay(a.showlink)');
            return this;
        },


        hide: function(i) {
            this.hiddenCells.include(i);
            i++;
            this.head.getElements(this.options.thSelector + ':nth-child(' + i + ') div').setStyle('display', 'none');
            this.head.getElements(this.options.thSelector + ':nth-child(' + i + ') .showlink').setStyle('display', '');
            this.body.getElements('tr td:nth-child(' + i + ')').each(function(td) {
                td.store('hiddenHtml', td.get('html'));
                td.set('html', '');
            });
            return false;
        },

        show: function(i) {
            this.hiddenCells.erase(i);
            i++;
            this.head.getElements(this.options.thSelector + ':nth-child(' + i + ') div').setStyle('display', '');
            this.head.getElements(this.options.thSelector + ':nth-child(' + i + ') .showlink').setStyle('display', 'none');
            this.body.getElements('tr td:nth-child(' + i + ')').each(function(td) {
                td.set('html', td.retrieve('hiddenHtml'));
            });
            return false;
        },

        headClick: function(event) {
            //clear unintended selections
            if (window.getSelection) {
                var s = window.getSelection();
                if (s) s.collapse(document.body, 0);
            }

            if (!$(event.target).hasClass('hidelink') && !$(event.target).hasClass('showlink'))
                this.parent.apply(this, arguments);
        }
    });


    var MetaTable = this.MetaTable = new Class({
        Extends: HideableTable,
        options: {
            thSelector: 'td.head_cell:not(.edit)',
            tableArguments: {}
        },

        initialize: function(table) {
            table = document.id(table);
            preformatTable(table);
            this.parent.apply(this, arguments);

            this.tableArgs = Object.merge({
                'args': '',
                'template': null,
                'autorefresh': false,
                'nametemplate': ''
            }, this.options.tableArguments);

            this.metaRequest = new Request.JSON({
                url: '?action=getMetaJSON',
                data: 'args=' + encodeURIComponent(this.tableArgs.args),
                onSuccess: function(json) {
                    this.metas = json;
                }.bind(this)
            });

            var selectors = [".meta_cell span:not(.edit)", ".meta_cell:not(.edit)"];
            this.body.addEvent('shiftclick:relay(' + selectors.join(", ") + ')', this.valueEdit.bind(this));

            this.head.addEvent('shiftclick:relay(span[id*=' + this.options.separator + '])', this.keyEdit.bind(this));

            table.addEvent('mouseover:once', function() {
                this.metaRequest.get()
            }.bind(this));

            if (this.tableArgs.autorefresh) {
                this.refresh.periodical(this.tableArgs.autorefresh * 1000, this, null);
            }

            var parent = table.getParent('div.metatable');
            if (parent && parent.getNext('a') && parent.getNext('a').get('text') == "[edit]") {
                new Element('a.jslink[text=[new row]]')
                    .setStyles({'font-size': 'inherit'})
                    .addEvent('click', this.newPage.bind(this))
                    .inject(parent, 'after');
            }

            this.enableSort();
            this.enableHiding();
        },

        setTable: function(tab) {
            tab = preformatTable(tab);

            this.head.getElements(this.options.thSelector).destroy();
            this.head.adopt(tab.getElement('thead').getElements(this.options.thSelector));

            this.body.getElements('tr').destroy();
            this.body.adopt(tab.getElement('tbody').getElements('tr'));

            this.setParsers();
            this.enableHiding();

            return this;
        },

        valueEdit: function(event) {
            event.preventDefault();

            if (this.metaRequest.isRunning()) {
                this.valueEdit.delay(100, this, event);
                return;
            }

            var target = document.id(event.target),
                key, id, index, page, oldValue = "";

            if (target.get('tag') == 'td') {
                //edit empty cells without existing value
                var i = target.getParent('tr').getElements('td.meta_cell').indexOf(target);
                id = unescapeId(this.head.getElements('span[id*=' + this.options.separator + ']')[i].get('id'));
                key = id.split(this.options.separator)[1];
                index = 0;
                page = target.getParent('tr').getFirst('td').get('text');

                if (target.children.length > 0) {
                    //append new value to existing ones if key had values
                    index = this.metas[page][key].length;
                    target = new Element('span').inject(target);
                }
            } else {
                //edit existing value
                if (target.get('tag') != 'span') target = target.getParent('span');

                id = unescapeId(target.get('id'));

                page = id.split(this.options.separator)[0];
                key = id.split(this.options.separator)[1];
                index = id.split(this.options.separator)[2];
                oldValue = this.metas[page][key][index];
            }

            if (this.inlineEditor) this.inlineEditor.cancel();

            var editor = this.inlineEditor = new InlineEditor(target, {
                autoFormat: false,
                oldValue: oldValue,
                key: key,

                onSave: function(value) {
                    if (!this.metas[page][key]) this.metas[page][key] = [""];

                    var oldData = {};
                    oldData[page] = {};
                    oldData[page][key] = Array.clone(this.metas[page][key]);

                    if (i >= this.metas[page][key].length) this.metas[page][key].push("");
                    this.metas[page][key][index] = value;

                    var args = {};
                    args[page] = {};
                    args[page][key] = this.metas[page][key];

                    new Request.SetMetas({
                        data: 'action=setMetaJSON&args=' + encodeURIComponent(JSON.encode(args)),
                        checkUrl: '?action=getMetaJSON&args=' + page,
                        checkData: oldData,
                        onSuccess: function() {
                            this.inlineEditor = null;
                            this.refresh();
                        }.bind(this),
                        onConflict: function() {
                            this.inlineEditor.cancel();
                            this.refresh();
                        }.bind(this)
                    }).checkAndSend();

                    editor.exit();
                }.bind(this)
            });
        },

        keyEdit: function(event) {
            event.stopPropagation();
            event.preventDefault();

            if (this.metaRequest.isRunning()) {
                this.keyEdit.delay(100, this, event);
                return;
            }

            var target = document.id(event.target);
            if (target.get('tag') != 'span') target = target.getParent('span');

            var id = unescapeId(target.get('id'));
            var oldKey = id.split(this.options.separator)[1];

            if (this.inlineEditor) this.inlineEditor.cancel();

            var parent = target.getParent('td').addClass('edit');

            var editor = this.inlineEditor = new InlineEditor(target, {
                autoFormat: false,
                oldValue: oldKey,
                onSave: function(newKey) {
                    var oldData = Object.map(Object.clone(this.metas), function(metas, page) {
                        var m = Object.subset(metas, [oldKey, newKey]);
                        if (!m[newKey]) m[newKey] = [];
                        return m;
                    });

                    var args = Object.map(this.metas, function(metas, page) {
                        var renamed = {};
                        renamed[newKey] = (metas[newKey] || []).combine(metas[oldKey]|| []);
                        renamed[oldKey] = [];
                        return renamed;
                    });

                    new Request.SetMetas({
                        data: 'action=setMetaJSON&args=' + encodeURIComponent(JSON.encode(args)),
                        checkUrl: '?action=getMetaJSON&args=' +  encodeURIComponent(this.tableArgs.args),
                        checkData: oldData,
                        onSuccess: function() {
                            this.inlineEditor = null;
                            this.refresh();
                        }.bind(this),
                        onConflict: function() {
                            this.inlineEditor.cancel();
                            this.refresh();
                        }.bind(this)
                    }).checkAndSend();

                    editor.exit();
                }.bind(this),
                onExit: function() {
                    parent.removeClass('edit');
                }
            });
        },

        newPage: function(event) {
            if (event) event.preventDefault();


            if (this.tableArgs.template && !this.template) {
                if (!this._templateRequest) {
                    this._templateRequest = new Request({
                        url: '?action=ajaxUtils&util=getTemplate&name=' + this.tableArgs.template,
                        onSuccess: function(txt) {
                            this.template = txt;
                            delete this['_templateRequest']
                        }.bind(this)
                    }).send();
                }
                this.newPage.delay(100, this);
                return;
            }
            var editor = new Editor({
                content: this.template,
                name: this.tableArgs.nametemplate,
                template: this.tableArgs.template
            });

            editor.addEvent('success', function() {
                this.refresh();
            }.bind(this))

        },

        refresh: function() {
            if (this.inlineEditor) return;

            var oldMetas = Object.clone(this.metas);

            this.metaRequest.get();

            new Request.HTML({
                url: '?action=showMetaTable',
                data: 'args=' + this.tableArgs.args,
                evalScripts: false,
                onSuccess: function(nodes) {
                    var tab = $$(nodes).getElement('table').filter(function(el) {
                        return el != null
                    });
                    if (tab.length != 1) return; //todo: show error message
                    this.setTable(tab[0]);
                    this.reSort();
                    this.hiddenCells.each(this.hide, this);

                    var highlightChanges = function(){
                        if (this.metaRequest.isRunning()) {
                            highlightChanges.delay(100);
                            return
                        }
                        diff(oldMetas, this.metas).each(function(page){
                            this.body.getElements('tr').each(function(row){
                               if (row.cells[0].get('text') == page) {
                                   row.highlight("#bfb");
                               }
                            });
                        }, this);
                    }.bind(this);

                    highlightChanges.delay(500);
                }.bind(this)

            }).send();
        }
    });


    var Editor = new Class({
        Extends: Overlay,
        options: {
            content: "",
            name: "",
            template: ""
        },

        build: function() {
            this.parent();

            var form = new Element('form').inject(this.editor);

            var namefield = new Element('input[name=pagename][placeholder=Page Name]')
                    .set('value', new Date().format(this.options.name))
                    .setStyles({'width': '200px', 'margin-left': '20px'});

            form.adopt(
                new Element('span[text=Pagename: ]'),
                namefield,
                new Element('br'),
                new Element('br')
            );

            if (this.options.template) {
                new Element('a',{
                    'text': 'create in metaformedit',
                    'target': '_blank',
                    'href': namefield.get('value') + '?action=editmetaform&template=' +this.options.template,
                    'styles': {
                        'margin-left': '10px'
                    },
                    'events': {
                        'click': function(){
                            this.cancel();
                        }.bind(this)
                    }
                }).inject(namefield, 'after')
            }

            this.textarea = new Element('textarea', {
                'value': this.options.content,
                'styles': {
                    'width': '100%',
                    'margin': 'auto'
                }
            }).inject(form);

            new DynamicTextarea(this.textarea, {
                minRows: 20
            });

            var controls = new Element('div').adopt(
                new Element('button', {
                    text: 'Save',
                    styles: {
                        'float': 'left'
                    },
                    events: {
                        'click': this.send.bind(this)
                    }
                }),
                new Element('div').setStyle('clear', 'both')
            ).inject(this.container)
        },

        send: function() {
            var page = this.editor.getElement('input[name=pagename]').value;

            var data = {
                action: 'ajaxUtils',
                util: 'newPage',
                page: page,
                content: this.textarea.get('value')
            };

            new Request.JSON({
                url: page,
                method: 'post',
                data: Object.toQueryString(data),
                onSuccess: function(response) {
                    if (response && response.status == "ok") {
                        this.fireEvent('success');
                        this.cancel();
                    } else {
                        alert("Failed to create new page!\n" + '"' + response.msg + '"');
                    }
                }.bind(this)
            }).send()
        }
    });

    var InterMetaTable = this.InterMetaTable = new Class({
        Extends: HideableTable,

        options: {
            selector: "",
            baseurl: "",
            sortable: true,
            collabs: [""],
            footer: false,
            inaccessibleCollabs: null
        },

        initialize: function(el, opts) {
            this.container = document.id(el);

            ["_format", "construct"].each(function(f){
                this[f].bind(this);
            }, this);

            this.parent.apply(this, [null, opts]);

            if (typeOf(this.options.collabs) == "string") this.options.collabs = [this.options.collabs];
            this.update();
        },

        build: function() {
            this.parent();
            this.inject(this.container);

            this.container.addClass('waiting');

            var denied = this.options.inaccessibleCollabs;
            if (denied) {
                this.container.grab(new Element('em', {
                    text: 'You do not have premission to access following collab' +
                        (denied.length > 1 ? "s" : "") + ': ' + denied,
                    styles: {
                        color: 'red'
                    }
                }), 'top');
            }

            //this.container.grab(new Element('a.jslink[text=[settings]]'), 'bottom')
        },

        _format: function(vals, f){
            if (typeOf(vals) != "array") vals = [vals];
            return vals.map(function(value){
                return f[value] || value;
            }, this)
        },

        construct: function(){
            this.empty();

            var keys = {};
            Object.each(this.metas, function(pages, collab) {
                Object.each(pages, function(metas, page) {
                    Object.keys(metas).each(function(key){
                        if (!keys[key]) keys[key] = this._format(key, this.formatted[collab])
                    }, this);
                }, this);
            }, this);

            var foots = {};
            Object.sortedKeys(keys).each(function(key){
                foots[key] = 0;
            });

            this.setHeaders(([new Element('a.jslink[text=edit]')].concat(Object.sortedValues(keys))));
            this.thead.rows[0].addClass('meta_header');

            Object.each(this.metas, function(pages, collab) {
                Object.each(pages, function(metas, page) {
                    var vals = [new Element('a', {
                        text: (collab? collab+ ':': "") + page,
                        href: this.options.baseurl + collab + '/' +page
                    })];

                    Object.sortedKeys(keys).each(function(key) {
                        if (!metas[key] || metas[key].length == 0) {
                            vals.push(" ");
                        } else {
                            vals.push(this._format(metas[key], this.formatted[collab]).join(", "));
                            if (Number.from(metas[key])) {
                                foots[key] += Number.from(metas[key]);
                            }else{
                                foots[key] = null;
                            }

                        }
                    }, this);

                    this.push(vals);
                }, this);
            }, this);

            $$(this.body.rows).getFirst('td').addClass('meta_page');
            $$($$(this.body.rows).getElements('td:not(.meta_page)')).addClass('meta_cell');

            if (this.options.footer) {
                if (Object.values(foots).clean().length)
                    this.setFooters([new ActionSelector({
                        "sum": function(){alert('sum')},
                        "alert": function(){alert('foo')}
                    }, this).toElement()].concat(Object.values(foots)));
            }
            this.sort(0, false);
            this.enableHiding();


            if (!this.isUpdating()) this.container.removeClass('waiting');
        },

        isUpdating: function(){
            if (!this.requests || this.requests.length == 0) return false;
            return this.requests.some(function(request){
                return request.isRunning();
            })
        },

        update: function() {
            if (this.isUpdating()) return;

            this.requests = [];
            this.options.collabs.each(function(collab) {
                this.requests.push(new Request.JSON({
                    url: this.options.baseurl + collab+ '/?action=getMetaJSON',
                    data: 'args=' + encodeURIComponent(this.options.selector) + '&formatted=true',
                    onSuccess: function(json) {
                        if (!this.metas) this.metas = {};
                        if (!this.formatted) this.formatted = {};
                        this.metas[collab] = json.metas;
                        this.formatted[collab] = json.formatted;
                        this.construct();
                    }.bind(this)
                }).get())
            }, this);
        }
    });
})();
