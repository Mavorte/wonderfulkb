---
title: "Case Client: před opravou live acceptance oddělit AWS identitu od transportních schopností"
date: 2026-10-19
category: tooling
component: backend
tags: [case-client, acceptance, aws-mcp, planning, transport]
file_type: checklist
---

Při plánování acceptance opravy task-beca6825 byl parent checkpoint důkazem pouze STS identity a offline lintu: 0 deploy, 0 HTTP a žádný deploy-target/write-opt-in RED. AWS MCP run_script nemá obecnou síť ani lokální build soubory, takže STS úspěch nepotvrzuje cestu pro upload Linux Zipu, privátní rollback download ani předání API klíče přímo do HTTPS procesu. Před prvním cutoverem ověřit podporované přenosy přes dostupné MCP funkce, bez návratu klíče či presigned URL do modelu; chybějící schopnost popsat konkrétně, neobcházet ji AWS CLI přes shell. V plánu oddělit tuto capability kontrolu od SDK oprávnění, lokálního venv bootstrapu a runtime proof. Zjištění pochází pouze z inspekce zadání, nástrojového kontraktu a checkpointu, nikoli z nového cloudového běhu.