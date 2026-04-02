# Clivi · Monitor de Precios Wegovy México

Dashboard de monitoreo de precios diarios para Wegovy (semaglutida) en 5 farmacias mexicanas, con visualización por dosis y actualización automática diaria.

**🌐 Ver dashboard:** [https://clivi-mx.github.io/wegovy-monitor](https://clivi-mx.github.io/wegovy-monitor)

---

## Farmacias monitoreadas

| Farmacia | URL |
|----------|-----|
| Farmacias Guadalajara | farmaciasguadalajara.com.mx |
| Farmacia del Ahorro | fahorro.com |
| Farmacias Benavides | benavides.com.mx |
| SFE — Servicios Farmacéuticos Especializados | pacientes.sfe.com.mx |
| Farmacias Similares | farmaciasimilares.com.mx |

## Dosis rastreadas

`0.25 mg` · `0.5 mg` · `1.0 mg` · `1.7 mg` · `2.4 mg`

---

## Estructura del repositorio

```
wegovy-monitor/
├── .github/
│   └── workflows/
│       └── daily-scrape.yml    # GitHub Actions cron diario
├── data/
│   └── prices.json             # Historial de precios (generado automáticamente)
├── docs/
│   └── index.html              # Dashboard (servido vía GitHub Pages)
├── scrapers/
│   ├── wegovy_scraper.py       # Scraper principal
│   └── seed_data.py            # Script de inicialización de datos
├── requirements.txt
└── README.md
```

---

## Setup inicial (una sola vez)

### 1. Clonar el repositorio

```bash
git clone https://github.com/clivi-mx/wegovy-monitor.git
cd wegovy-monitor
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Generar datos iniciales (seed)

```bash
python scrapers/seed_data.py
```

Esto crea `data/prices.json` con 30 días de historial simulado para que el dashboard no arranque vacío.

### 4. Probar el scraper localmente

```bash
python scrapers/wegovy_scraper.py
```

---

## Activar GitHub Pages

1. En GitHub → Settings → Pages
2. Source: **Deploy from a branch**
3. Branch: `main` / Folder: `/docs`
4. Guardar → URL disponible en `https://<usuario>.github.io/wegovy-monitor`

---

## Automatización diaria (GitHub Actions)

El workflow `.github/workflows/daily-scrape.yml` corre automáticamente todos los días a las **03:00 hora de México** (09:00 UTC).

El bot:
1. Ejecuta `wegovy_scraper.py`
2. Actualiza `data/prices.json`
3. Hace commit y push con el mensaje `chore: update Wegovy prices YYYY-MM-DD`

No se requiere servidor ni costo adicional — corre gratis en GitHub Actions (hasta 2,000 minutos/mes en plan free).

### Trigger manual

Desde GitHub → Actions → "Daily Wegovy Price Scraper" → Run workflow.

---

## Agregar una nueva farmacia

1. Añadir entrada en `PHARMACIES` (en `docs/index.html` y `scrapers/wegovy_scraper.py`)
2. Agregar `BASE_PRICES` de referencia
3. Configurar `SEARCH_CONFIG` con URL y selectores CSS
4. Hacer push — el siguiente cron incluirá la nueva farmacia

---

## Características del dashboard

- Gráfica de serie de tiempo por dosis por farmacia (últimos 30 días)
- % cambio vs día anterior
- Badge "★ Más barato" por dosis
- Alertas automáticas para caídas > 3%
- Exportación a CSV
- Actualización automática diaria sin backend

---

## Stack

- **Frontend:** HTML + Chart.js (sin framework, sin build step)
- **Scraper:** Python + Playwright + BeautifulSoup
- **Storage:** JSON en repo (sin base de datos)
- **Hosting:** GitHub Pages (gratis)
- **Automation:** GitHub Actions (gratis)

---

Construido por el equipo de Growth de **[Clivi](https://clivi.com.mx)** · Especialistas en tratamientos GLP-1 en México.
