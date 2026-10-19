---
title: "Case Client: boto3 Decimal context nestačí k validaci čísel"
date: 2026-10-19
category: runtime-errors
component: backend
tags: [case-client, dynamodb, decimal, serialization]
file_type: rules
---

Při offline implementaci DynamoDB adaptéru prošla samotným boto3 TypeSerializerem čísla Decimal(1e126) a Decimal(1e-131), která jsou mimo požadovaný číselný rozsah DynamoDB. Regresní preflight test bez očekávaného SDK volání zachytil, že taková metadata pokračovala až do GetItem. Adaptér nyní před jakýmkoli DB voláním kromě TypeSerializer/context kontroluje konečnost a u nenulového čísla exponent adjusted v intervalu -130 až 125; přesnost dále hlídají Decimal traps serializeru. JSON requesty jsou parsované přes simplejson use_decimal=True, odpověď nepřevádí Decimal na float ani string. Přímý konečný Python float se převádí přes Decimal(str(value)), nikoli přes binární Decimal(float). NaN/Infinity, příliš přesná či mimo rozsah čísla se odmítnou před zápisem. Testováno přes skutečný handler a botocore Stubber; nejde o důkaz živé cloudové persistence.