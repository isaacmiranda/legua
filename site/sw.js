/* Service worker da Légua: deixa o site funcionar sem rede depois da primeira visita. Só guarda arquivos do próprio site (mesma
 * origem). Pedidos a outros domínios (tiles do OpenStreetMap, tiles de elevação da AWS) NÃO passam por aqui: não são guardados
 * nem interceptados, para não manter cópia de regiões vistas e para respeitar a política de uso desses serviços.
 * Estratégia: responde do cache e atualiza em segundo plano ("stale-while-revalidate"); a versão do cache muda a cada release. */
"use strict";
var VERSAO = "legua-sw-1";
var ARQUIVOS = [
  "./", "index.html", "enlace.html", "consolidado.html", "style.css", "manifest.webmanifest", "icone.svg",
  "data.js", "app.js", "nav.js", "citar.js", "evidencia.js", "explica.js", "estimator.js", "perfil_c.js",
  "calculadoras.js", "calc_ui.js", "pacote.js", "pacote_ui.js", "medicoes.js", "medicoes_ui.js", "sensibilidade.js", "sensibilidade_ui.js",
  "rastros.js", "rastros_ui.js", "spec_ui.js", "especificacao.js",
  "propagacao.js", "terreno.js", "terrarium.js", "mapa.js", "enlace.js", "enlace_pagina.js",
  "vetores/frames.txt", "vetores/mic.txt"
];

self.addEventListener("install", function (ev) {
  ev.waitUntil(caches.open(VERSAO).then(function (c) { return Promise.all(ARQUIVOS.map(function (a) { return c.add(a).catch(function () { /* arquivo opcional ausente */ }); })); }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener("activate", function (ev) {
  ev.waitUntil(caches.keys().then(function (ks) { return Promise.all(ks.filter(function (k) { return k.indexOf("legua-sw-") === 0 && k !== VERSAO; }).map(function (k) { return caches.delete(k); })); }).then(function () { return self.clients.claim(); }));
});
self.addEventListener("fetch", function (ev) {
  var req = ev.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) return;          // outras origens: direto à rede, sem cache
  ev.respondWith(caches.open(VERSAO).then(function (c) {
    return c.match(req, { ignoreSearch: true }).then(function (hit) {
      var rede = fetch(req).then(function (r) { if (r && r.ok) c.put(req, r.clone()); return r; }).catch(function () { return hit; });
      return hit || rede;
    });
  }));
});
