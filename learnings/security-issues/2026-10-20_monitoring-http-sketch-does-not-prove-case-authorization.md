---
title: "Monitoring HTTP: sketch route testu neprokazuje case autorizaci"
date: 2026-10-20
category: security-issues
component: backend
tags: [monitoring, authorization, tdd, planning]
file_type: rules
---

Při plánování document-events GET byl starý test `be-intake/tests/test_processing_monitor_routes.py` pouze sketch: HTTP 200 se sdíleným `x-api-key` by dokazovalo existenci route, nikoli oprávnění identity ke konkrétnímu case. Před tvorbou autorizovaného happy-path RED/GREEN je potřeba identifikovat vlastníka a skutečné service-side identity→case rozhodnutí i schválenou syntetickou fixture. Pokud rozhraní neexistuje, plán musí zastavit registraci/deploy endpointu a přesně zapsat blocker, nikoli použít permissive test double. Pro nezávislý první RED lze ověřovat `Cache-Control: private, no-store` na neautentizované odpovědi dané monitorovací cesty, ale zachytit jej až po ověření závislostí a autorizace; sám nikdy nedokazuje bezpečnou 200 větev.
