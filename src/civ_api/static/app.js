// Icom CI-V Explorer — front-end logic.
// Security notes:
//  - All API-sourced text is inserted via textContent / DOM APIs, never
//    innerHTML, so stored markup in the reference data or feedback cannot
//    execute. This is the primary XSS defence and must be preserved.
//  - No use of eval, Function(), document.write, or inline event handlers.
//  - All requests go to same-origin endpoints only (CSP connect-src 'self').
//  - URL parameters are built with URLSearchParams to avoid injection.
(function () {
  "use strict";

  var BASE = "";  // same origin

  // ---- tiny helpers -------------------------------------------------------
  function el(id) { return document.getElementById(id); }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function tag(name, text, attrs) {
    var n = document.createElement(name);
    if (text != null) n.textContent = text;
    if (attrs) for (var k in attrs) {
      if (k === "class") n.className = attrs[k];
      else n.setAttribute(k, attrs[k]);
    }
    return n;
  }

  function getJSON(url, params) {
    var u = new URL(BASE + url, window.location.origin);
    if (params) for (var k in params) {
      if (params[k] !== "" && params[k] != null) u.searchParams.set(k, params[k]);
    }
    return fetch(u.toString()).then(function (r) {
      if (!r.ok) return r.text().then(function (t) { throw new Error(t || r.statusText); });
      return r.json();
    });
  }

  function postJSON(url, body) {
    return fetch(BASE + url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) {
      if (!r.ok) return r.text().then(function (t) { throw new Error(t || r.statusText); });
      return r.json();
    });
  }

  // ---- tabs ---------------------------------------------------------------
  var tabs = Array.prototype.slice.call(document.querySelectorAll(".tab-btn"));
  var panels = Array.prototype.slice.call(document.querySelectorAll(".tab-panel"));

  tabs.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var name = btn.getAttribute("data-tab");
      tabs.forEach(function (b) {
        var on = b === btn;
        b.classList.toggle("active", on);
        b.setAttribute("aria-selected", on ? "true" : "false");
      });
      panels.forEach(function (p) {
        p.classList.toggle("active", p.id === "tab-" + name);
      });
    });
  });

  // ---- radios -------------------------------------------------------------
  var radiosCache = [];

  function loadRadios() {
    getJSON("/radios").then(function (radios) {
      radiosCache = radios;
      var tbody = el("radios-table").querySelector("tbody");
      clear(tbody);

      // populate selects used by other tabs
      var cmdSel = el("radio-select");
      var fbSel = el("fb-radio");
      var browseSel = el("browse-radio");
      clear(cmdSel); clear(fbSel); clear(browseSel);
      cmdSel.appendChild(tag("option", "All radios", { value: "" }));
      browseSel.appendChild(tag("option", "Select a radio…", { value: "" }));
      radios.forEach(function (r) {
        cmdSel.appendChild(tag("option", r.id + " — " + r.name, { value: r.id }));
        fbSel.appendChild(tag("option", r.id + " — " + r.name, { value: r.id }));
        browseSel.appendChild(tag("option", r.id + " — " + r.name, { value: r.id }));
      });

      radios.forEach(function (r) {
        var tr = document.createElement("tr");
        tr.appendChild(tag("td", r.id));
        tr.appendChild(tag("td", r.name));
        tr.appendChild(tag("td", r.address));
        tr.appendChild(tag("td", String(r.command_count)));
        var cell = tag("td");
        var btn = tag("button", "View", { type: "button", "data-rid": r.id });
        btn.addEventListener("click", function () { showRadioDetail(r.id); });
        cell.appendChild(btn);
        tr.appendChild(cell);
        tbody.appendChild(tr);
      });
    }).catch(function (err) {
      var tbody = el("radios-table").querySelector("tbody");
      clear(tbody);
      tbody.appendChild(tag("tr", "", {})).appendChild(tag("td", "Error: " + err.message));
    });
  }

  function showRadioDetail(rid) {
    Promise.all([
      getJSON("/radios/" + encodeURIComponent(rid)),
      getJSON("/radios/" + encodeURIComponent(rid) + "/capabilities")
    ]).then(function (results) {
      var radio = results[0];
      var caps = results[1];
      var box = el("radio-detail");
      clear(box);
      box.hidden = false;

      box.appendChild(tag("h3", radio.name + " (" + radio.id + ")"));
      box.appendChild(tag("p", "Default CI-V address: " + radio.address + "  |  Commands loaded: " + radio.command_count));

      box.appendChild(tag("h4", "Capabilities (" + caps.length + ")"));
      var table = tag("table", null, { class: "caps-table" });
      var thead = tag("thead");
      thead.appendChild(tag("tr", null, {}))
        .appendChild(tag("th", "Capability"));
      var headRow = thead.firstChild;
      headRow.appendChild(tag("th", "Value"));
      headRow.appendChild(tag("th", "Evidence"));
      headRow.appendChild(tag("th", ""));
      table.appendChild(thead);
      var tbody = tag("tbody");
      caps.forEach(function (c) {
        var val = c.radios[radio.id];
        var isFalse = val === false || val === "false" || val === "False";
        var tr = tag("tr", null, { class: isFalse ? "cap-false" : "" });
        tr.appendChild(tag("td", c.name));
        var valCell = tag("td", String(val));
        if (!isFalse) valCell.className = "cap-true";
        tr.appendChild(valCell);
        tr.appendChild(tag("td", c.command_evidence));
        var cell = tag("td");
        var link = tag("a", "Feedback", { href: "#feedback" });
        link.addEventListener("click", function (ev) {
          ev.preventDefault();
          switchTab("feedback");
          prefillCapabilityFeedback(radio.id, c);
        });
        cell.appendChild(link);
        tr.appendChild(cell);
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      box.appendChild(table);
    }).catch(function (err) {
      var box = el("radio-detail");
      clear(box);
      box.hidden = false;
      box.appendChild(tag("p", "Error: " + err.message));
    });
  }

  // ---- commands -----------------------------------------------------------
  function runSearch(ev) {
    ev.preventDefault();
    var params = {
      radio_id: el("radio-select").value,
      q: el("search-q").value,
      limit: "100",
      offset: "0"
    };
    getJSON("/commands", params).then(function (data) {
      el("search-meta").textContent = data.total + " result" + (data.total === 1 ? "" : "s") +
        (data.query ? " for \"" + data.query + "\"" : "") +
        (data.radio_id ? " on " + data.radio_id : "") + ".";
      var tbody = el("commands-table").querySelector("tbody");
      clear(tbody);
      data.items.forEach(function (c) {
        var tr = document.createElement("tr");
        tr.appendChild(tag("td", c.radio_id));
        tr.appendChild(tag("td", c.cmd));
        tr.appendChild(tag("td", c.sub_cmd));
        tr.appendChild(tag("td", c.data));
        tr.appendChild(tag("td", c.description));
        var cell = tag("td");
        var link = tag("a", "Feedback", { href: "#feedback", "data-cmd": "" });
        link.addEventListener("click", function (ev) {
          ev.preventDefault();
          switchTab("feedback");
          prefillFeedback(c);
        });
        cell.appendChild(link);
        tr.appendChild(cell);
        tbody.appendChild(tr);
      });
      if (!data.items.length) {
        var tr = document.createElement("tr");
        tr.appendChild(tag("td", "No commands found."));
        tr.firstChild.colSpan = 6;
        tbody.appendChild(tr);
      }
    }).catch(function (err) {
      el("search-meta").textContent = "Error: " + err.message;
    });
  }

  // ---- feedback -----------------------------------------------------------
  function switchTab(name) {
    var btn = document.querySelector('.tab-btn[data-tab="' + name + '"]');
    if (btn) btn.click();
  }

  function prefillFeedback(cmd) {
    el("fb-radio").value = cmd.radio_id;
    el("fb-cmd").value = cmd.cmd || "";
    el("fb-subcmd").value = cmd.sub_cmd || "";
    el("fb-field").value = "description";
    el("fb-capname").value = "";
    el("fb-value").value = "";
    el("fb-notes").value = "";
    el("fb-submitter").value = "";
    var box = el("feedback-result");
    box.hidden = true;
    clear(box);
    el("fb-value").focus();
  }

  function prefillCapabilityFeedback(rid, cap) {
    el("fb-radio").value = rid;
    el("fb-cmd").value = "";
    el("fb-subcmd").value = "";
    el("fb-field").value = "capability";
    el("fb-capname").value = cap.name;
    el("fb-value").value = "";
    el("fb-notes").value = "";
    el("fb-submitter").value = "";
    var box = el("feedback-result");
    box.hidden = true;
    clear(box);
    el("fb-value").focus();
  }

  function submitFeedback(ev) {
    ev.preventDefault();
    var box = el("feedback-result");
    box.hidden = false;
    clear(box);
    box.className = "result";
    box.appendChild(tag("p", "Submitting..."));

    var body = {
      radio_id: el("fb-radio").value,
      cmd: el("fb-cmd").value,
      sub_cmd: el("fb-subcmd").value,
      field: el("fb-field").value,
      capability_name: el("fb-capname").value,
      suggested_value: el("fb-value").value,
      notes: el("fb-notes").value,
      submitter: el("fb-submitter").value
    };
    postJSON("/feedback", body).then(function (ack) {
      clear(box);
      box.className = "result ok";
      box.appendChild(tag("p", "Feedback received (id " + ack.id + "). Thank you!"));
      el("feedback-form").reset();
    }).catch(function (err) {
      clear(box);
      box.className = "result err";
      box.appendChild(tag("p", "Submission failed: " + err.message));
    });
  }

  // ---- browse ------------------------------------------------------------
  var browseCache = {};  // radio_id -> { byCmd: {cmd: [Command]}, order: [cmd] }

  function loadBrowseRadio(rid) {
    var codesBox = el("browse-codes");
    var detail = el("browse-detail");
    detail.hidden = true; clear(detail);
    if (!rid) { codesBox.hidden = true; clear(codesBox); return; }

    if (browseCache[rid]) {
      renderBrowseCodes(rid, browseCache[rid]);
      return;
    }
    codesBox.hidden = false; clear(codesBox);
    codesBox.appendChild(tag("p", "Loading commands…", { class: "meta" }));

    // Page through every command for this radio. The endpoint caps each page
    // at 500 rows, but some radios (e.g. IC-9700) have more, so loop until the
    // running total is reached — otherwise higher-numbered codes are dropped.
    function fetchAll(rid) {
      var PAGE = 500;
      var collected = [];
      function page(offset) {
        return getJSON("/radios/" + encodeURIComponent(rid) + "/commands", {
          limit: String(PAGE), offset: String(offset)
        }).then(function (data) {
          collected = collected.concat(data.items);
          if (collected.length < data.total) {
            return page(offset + PAGE);
          }
          return collected;
        });
      }
      return page(0);
    }

    fetchAll(rid)
      .then(function (items) {
        var byCmd = {};
        var order = [];
        items.forEach(function (c) {
          if (!byCmd[c.cmd]) { byCmd[c.cmd] = []; order.push(c.cmd); }
          byCmd[c.cmd].push(c);
        });
        // sort command codes numerically by hex value, fallback to string
        order.sort(function (a, b) {
          var ai = parseInt(a, 16), bi = parseInt(b, 16);
          if (isNaN(ai) || isNaN(bi)) return a < b ? -1 : (a > b ? 1 : 0);
          return ai - bi;
        });
        browseCache[rid] = { byCmd: byCmd, order: order };
        renderBrowseCodes(rid, browseCache[rid]);
      })
      .catch(function (err) {
        clear(codesBox);
        codesBox.appendChild(tag("p", "Error: " + err.message, { class: "meta" }));
      });
  }

  function renderBrowseCodes(rid, index) {
    var codesBox = el("browse-codes");
    codesBox.hidden = false;
    clear(codesBox);
    codesBox.appendChild(tag("p", index.order.length + " command codes. Click a code to see its sub-commands.", { class: "meta" }));
    var grid = tag("div", null, { class: "code-grid" });
    index.order.forEach(function (cmd) {
      var rows = index.byCmd[cmd];
      var btn = tag("button", cmd, { type: "button", class: "code-chip", "data-rid": rid, "data-cmd": cmd });
      btn.title = rows.length + " row" + (rows.length === 1 ? "" : "s");
      btn.addEventListener("click", function () { showBrowseDetail(rid, cmd, rows); });
      grid.appendChild(btn);
    });
    codesBox.appendChild(grid);
  }

  function showBrowseDetail(rid, cmd, rows) {
    var detail = el("browse-detail");
    clear(detail);
    detail.hidden = false;
    detail.appendChild(tag("h3", "Cmd " + cmd + " — " + rid + " (" + rows.length + " row" + (rows.length === 1 ? "" : "s") + ")"));
    var back = tag("button", "Back to codes", { type: "button", class: "back-btn" });
    back.addEventListener("click", function () { detail.hidden = true; });
    detail.appendChild(back);

    var table = tag("table", null, { class: "browse-table" });
    var thead = tag("thead");
    var hr = tag("tr", null, {});
    hr.appendChild(tag("th", "Sub cmd"));
    hr.appendChild(tag("th", "Data"));
    hr.appendChild(tag("th", "Description"));
    hr.appendChild(tag("th", ""));
    thead.appendChild(hr);
    table.appendChild(thead);
    var tbody = tag("tbody");
    rows.forEach(function (c) {
      var tr = tag("tr", null, {});
      tr.appendChild(tag("td", c.sub_cmd));
      tr.appendChild(tag("td", c.data));
      tr.appendChild(tag("td", c.description));
      var cell = tag("td");
      var link = tag("a", "Feedback", { href: "#feedback" });
      link.addEventListener("click", function (ev) {
        ev.preventDefault();
        switchTab("feedback");
        prefillFeedback(c);
      });
      cell.appendChild(link);
      tr.appendChild(cell);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    detail.appendChild(table);
  }

  // ---- copy-to-clipboard on docs code blocks -------------------------------
  // Injects a "Copy" button into each <pre> in the docs tab. Uses textContent
  // only (no innerHTML). The button reads the <pre>'s text content (its <code>
  // child) and copies it to the clipboard.
  function setupCopyButtons() {
    var docs = el("tab-docs");
    if (!docs) return;
    var pres = Array.prototype.slice.call(docs.querySelectorAll("pre"));
    pres.forEach(function (pre) {
      // Wrap the <pre> so the copy button stays pinned while code scrolls.
      var wrap = tag("div", null, { class: "pre-wrap" });
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(pre);

      var btn = tag("button", null, { type: "button", class: "copy-btn", "aria-label": "Copy code to clipboard", title: "Copy code to clipboard" });
      var label = tag("span", "Copy");
      // Build the copy icon via DOM APIs (never innerHTML — XSS defence invariant).
      var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 16 16");
      svg.setAttribute("aria-hidden", "true");
      var p1 = document.createElementNS("http://www.w3.org/2000/svg", "path");
      p1.setAttribute("d", "M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 010 1.5h-1.5a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-1.5a.75.75 0 011.5 0v1.5A1.75 1.75 0 018.75 16h-7.5A1.75 1.75 0 010 14.25v-7.5z");
      var p2 = document.createElementNS("http://www.w3.org/2000/svg", "path");
      p2.setAttribute("d", "M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0114.25 11h-7.5A1.75 1.75 0 015 9.25v-7.5zm1.75-.25a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-7.5a.25.25 0 00-.25-.25h-7.5z");
      svg.appendChild(p1);
      svg.appendChild(p2);
      btn.appendChild(svg);
      btn.appendChild(label);
      btn.addEventListener("click", function () {
        var code = pre.querySelector("code");
        var text = (code ? code : pre).textContent || "";
        function done() {
          label.textContent = "Copied";
          btn.classList.add("copied");
          setTimeout(function () {
            label.textContent = "Copy";
            btn.classList.remove("copied");
          }, 1500);
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done).catch(function () {});
        } else {
          var ta = document.createElement("textarea");
          ta.value = text;
          ta.style.position = "fixed";
          ta.style.opacity = "0";
          document.body.appendChild(ta);
          ta.select();
          try { document.execCommand("copy"); done(); } catch (e) {}
          document.body.removeChild(ta);
        }
      });
      wrap.appendChild(btn);
    });
  }

  // ---- wire up ------------------------------------------------------------
  el("search-form").addEventListener("submit", runSearch);
  el("feedback-form").addEventListener("submit", submitFeedback);
  el("browse-radio").addEventListener("change", function () {
    loadBrowseRadio(el("browse-radio").value);
  });
  setupCopyButtons();
  loadRadios();
})();