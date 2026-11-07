# Simple-ESP32-Plant-Health-Tracker

A small plant monitor for a potted mint. It reads soil moisture, temperature and humidity, works out a **health score** from published growing conditions, shows it on an OLED with an animated plant face, and sends **push notifications** to your phone with [ntfy](https://ntfy.sh) when the soil or temperature needs attention.

### Screen states

<p align="center">
  <img width="1200" height="444" alt="screen_states" src="https://github.com/user-attachments/assets/dda5b422-a2a1-4e51-a7a7-023eb293ef36" />
</p>

### Animation

<p align="center"> <img width="1200" alt="screen_animation" src="https://github.com/user-attachments/assets/42695507-2801-4aaa-938f-5cb757a854f1" /> </p>

## Features

- Calibrated soil moisture (%) from a capacitive sensor
- Temperature and humidity from a DHT11
- Health score from 0 to 100% based on mint's ideal ranges, with sources
- Humidity scored as **VPD** (vapour-pressure deficit), so the ideal humidity adjusts to the temperature
- 128×64 OLED UI: readings, health bar, state label, and an animated pot with a face (happy, thirsty, too hot, too cold, too wet, dry air)
- Push notifications through ntfy
- Everything in one `main.py`: download, connect and try it out!

## Hardware

| Part | Notes |
|---|---|
| ESP32 dev board (30-pin, CH340 USB) | MicroPython v1.29 |
| Capacitive soil moisture sensor | for soil moisture |
| DHT11 | temperature and humidity |
| 0.96" SSD1306 OLED, 128×64, I2C | two-colour model: the top 16 rows are yellow, the rest blue |
| 3× AA battery holder (optional) | or a USB power bank |

## Wiring

All four data pins sit next to each other on the left side of the board (D35, D32, D33, D25).

| Part | Pin | ESP32 |
|---|---|---|
| Soil sensor | AOUT | **D35** |
| OLED | SDA | **D32** |
| OLED | SCK/SCL | **D33** |
| DHT11 | DATA | **D25** |
| All sensors | VCC | **3V3** |
| All sensors | GND | **GND** |

<p align="center">
  <img width="360" alt="wiring" src="https://github.com/user-attachments/assets/f92f9726-34d2-47ab-9e6f-e9fb8a33568d" />
</p>

If you're using a battery pack, solder it as follows: white is GND, and red goes to **VIN**. Keep the sensors on **3.3V**. The ESP32 dev board has a built-in voltage regulator that steps the battery voltage down to 3.3V.

## Software setup

1. Flash **MicroPython** onto the ESP32 (v1.29 was used here).
2. Edit the settings near the top of `main.py`:

   ```python
   WIFI_NAME = "your-wifi-name"      # must be a 2.4 GHz network
   WIFI_PASS = "your-wifi-password"
   TOPIC = "your-random-topic"       # same topic as in the ntfy app
   ```

3. Upload `main.py` and the default `boot.py` to the board, then press **EN** to restart.

## Soil calibration

<p align="center">
  <img width="270" alt="calibration_setup" src="https://github.com/user-attachments/assets/a9279324-3464-4041-9264-05c45d552882" />
  <img width="580" alt="calibration_graph" src="https://github.com/user-attachments/assets/335b2bf4-128a-4489-92a8-e75fc6584258" />
</p>

The capacitive sensor gives a voltage, and the relationship between that voltage and actual moisture depends on the sensor, the soil and the supply voltage. So the sensor was calibrated against weighed soil.

**Method:** start with 100 g of air-dried soil. Add water in 5 g steps, mixing well after each step, and record the sensor voltage with `calibration/calib_logger.py`. Graph it, get the slope, and find the relationship between voltage and water (%) for your specific mix of soil, your voltage, and your sensor.

<p align="center"><img src="https://latex.codecogs.com/svg.image?%5Cbg%7Bwhite%7D%5Clarge%20%5Ctheta_g%20%3D%20%5Cfrac%7Bm_%7B%5Ctext%7Bwater%7D%7D%7D%7Bm_%7B%5Ctext%7Bdry%20soil%7D%7D%7D" alt="equation"></p>

| Total weight (g) | Water (%) | Volts (V) | Note |
|---|---|---|---|
| 100 | 0 | 3.139 | excluded (air-dry, top of the sensor's range) |
| 105 | 5 | 2.449 | |
| 110 | 10 | 2.373 | |
| 115 | 15 | 2.110 | |
| 120 | 20 | 2.056 | |
| 125 | 25 | 1.898 | |
| 130 | 30 | 1.849 | |
| 135 | 35 | 1.489 | |
| 140 | 40 | 1.424 | |
| 145 | 45 | 1.696 | excluded (saturated, reading turns around) |

**Fit**, water as a function of volts, over 5–40%:

<p align="center"><img src="https://latex.codecogs.com/svg.image?%5Cbg%7Bwhite%7D%5Clarge%20%5Ctheta_g%20%3D%200.8594%20-%200.3243%5C%2CV%20%5Cqquad%20R%5E2%20%3D%200.968" alt="equation"></p>

In code:

```python
v = soil.read_uv() / 1e6              # volts
pct = (0.8594 - 0.3243 * v) * 100     # water %
pct = max(0, pct)                     # dry soil reads above the calibrated range, so clamp at 0
```

The fit is only valid between about 1.42 and 2.45 V. Outside that, the values are extrapolated.

---

## Health score

Each factor gets a score from 0 to 1. It's **1 inside the ideal range**, **0 at the limits**, and a straight line in between, with one line for each side:

<p align="center"><img src="https://latex.codecogs.com/svg.image?%5Cbg%7Bwhite%7D%5Clarge%20S%20%3D%20%5Cmax%5Cbig%280%2C%5C%20%5Cmin%281%2C%5C%20%5Ctext%7Brising%20line%7D%2C%5C%20%5Ctext%7Bfalling%20line%7D%29%5Cbig%29" alt="equation"></p>

**The final health is the plain average**, shown as a percentage:

<p align="center"><img src="https://latex.codecogs.com/svg.image?%5Cbg%7Bwhite%7D%5Clarge%20%5Ctext%7Bhealth%7D%20%3D%20%5Cfrac%7BS_%7B%5Ctext%7Btemp%7D%7D%20%2B%20S_%7B%5Ctext%7Bhum%7D%7D%20%2B%20S_%7B%5Ctext%7Bsoil%7D%7D%7D%7B3%7D%20%5Ctimes%20100" alt="equation"></p>

### Temperature

| Point | °C | °F | Score | Source |
|---|---|---|---|---|
| Absolute min | 4 | 39 | 0 | Ecocrop |
| Optimal min | 15 | 59 | 1 | Ecocrop, OMAFRA |
| Optimal max | 25 | 77 | 1 | Ecocrop, OMAFRA |
| Absolute max | 35 | 95 | 0 | Ecocrop |

<p align="center"><img src="https://latex.codecogs.com/svg.image?%5Cbg%7Bwhite%7D%5Clarge%20S_T%20%3D%20%5Cmax%5Cbig%280%2C%5C%20%5Cmin%281%2C%5C%200.0909%5C%2CT%20-%200.3636%2C%5C%20-0.1%5C%2CT%20%2B%203.5%29%5Cbig%29" alt="equation"></p>

Above 25 °C, mint's essential-oil quality drops (OMAFRA), and maximum photosynthesis was measured at 20 °C (Clark 1981).

<p align="center">
  <img width="700" alt="temperature_score" src="https://github.com/user-attachments/assets/a8f9cd1c-1255-42e0-a335-eaf4cf268087" />
</p>

### Humidity, scored as VPD

Relative humidity on its own is misleading, because 50% RH at 15 °C and 50% RH at 30 °C dry out a plant very differently. **VPD** (vapour-pressure deficit) captures this: it's how much more water the air could still hold.

<p align="center"><img src="https://latex.codecogs.com/svg.image?%5Cbg%7Bwhite%7D%5Clarge%20e_s%28T%29%20%3D%200.6108%5C%2C%5Cexp%5C%21%5Cleft%28%5Cfrac%7B17.27%5C%2CT%7D%7BT%20%2B%20237.3%7D%5Cright%29%5C%20%5Ctext%7BkPa%7D%20%5Cqquad%20%5Ctext%7BVPD%7D%20%3D%20e_s%28T%29%5Cleft%281%20-%20%5Cfrac%7BRH%7D%7B100%7D%5Cright%29" alt="equation"></p>

| Point | VPD (kPa) | Score | Source |
|---|---|---|---|
| Too humid | 0.3 | 0 | Tucker & Runkle 2025 (mint was shortest at 0.3 kPa) |
| Target range starts | 0.7 | 1 | Runkle, MSU |
| Target range ends | 1.5 | 1 | Runkle, MSU |
| Too dry | 2.5 | 0 | **assumption**, since no source gives a dry-air limit |

<p align="center"><img src="https://latex.codecogs.com/svg.image?%5Cbg%7Bwhite%7D%5Clarge%20S_%7B%5Ctext%7BVPD%7D%7D%20%3D%20%5Cmax%5Cbig%280%2C%5C%20%5Cmin%281%2C%5C%202.5%5C%2Cv%20-%200.75%2C%5C%20-v%20%2B%202.5%29%5Cbig%29" alt="equation"></p>

The ideal humidity depends on temperature:

| Temp | e<sub>s</sub> (kPa) | Ideal RH | Too humid above |
|---|---|---|---|
| 15 °C | 1.71 | 12–59% | 82% |
| 20 °C | 2.34 | 36–70% | 87% |
| 25 °C | 3.17 | 53–78% | 91% |
| 30 °C | 4.24 | 65–84% | 93% |
| 35 °C | 5.62 | 73–88% | 95% |
| 40 °C | 7.38 | 80–91% | 96% |

The hotter it is, the more humid the air has to be to grow a healthy plant.

<p align="center">
  <img width="700" alt="vpd_score" src="https://github.com/user-attachments/assets/9f3bbb68-1924-4269-8dd8-77f78df6a76b" />
</p>

### Soil

The sources give soil limits as a fraction of **field capacity** (FC): how wet the soil is after watering and draining for 24 h. FC is **assumed to be 35%** on this sensor's scale, and saturation is **45%**, taken from the calibration above.

| Point | Soil (%) | Score | Source |
|---|---|---|---|
| 25% of FC, severe stress | 9 | 0 | *Mentha piperita* pot study |
| 75% of FC, mild stress | 26 | 1 | *Mentha piperita* pot study (scoring it 1 is a choice) |
| 100% of FC, best growth | 35 | 1 | Peppermint drought study |
| Saturated | 45 | 0 | calibration data; OMAFRA: mint dies in saturated soil |

<p align="center"><img src="https://latex.codecogs.com/svg.image?%5Cbg%7Bwhite%7D%5Clarge%20S_%7B%5Ctext%7Bsoil%7D%7D%20%3D%20%5Cmax%5Cbig%280%2C%5C%20%5Cmin%281%2C%5C%200.0588%5C%2Cp%20-%200.5294%2C%5C%20-0.1%5C%2Cp%20%2B%204.5%29%5Cbig%29" alt="equation"></p>

<p align="center">
  <img width="700" alt="soil_score" src="https://github.com/user-attachments/assets/8b6fbe61-cc20-4941-a75f-f7d4f4718b0d" />
</p>

### State (the label and the animation)

The state names whichever factor is **dragging the average down the most**, and which way it's off:

```python
worst = min(temp_score, hum_score, soil_score)
if worst >= 0.5:           return "happy"
if worst == soil_score:    return "thirsty" if pct < 26 else "wet"
if worst == temp_score:    return "hot" if t > 25 else "cold"
return "dry" if vpd(t, h) > 1.5 else "humid"
```

The `0.5` threshold means small dips (for example 27 °C, which scores 0.8) still show as Happy. The health bar still shows the exact percentage.

| Health | Meaning |
|---|---|
| 90–100% | healthy |
| 70–90% | stressed: fix the factor named on the label |
| below 70% | something is failing: act now |

A plant with bone-dry soil but perfect air still shows 67%, so trust the label as well as the bar.

---

## Screen

<p align="center">
  <img width="1200" height="444" alt="screen_states" src="https://github.com/user-attachments/assets/dda5b422-a2a1-4e51-a7a7-023eb293ef36" />
</p>

| Rows (y) | Content |
|---|---|
| 0–10 | Title (sits in the yellow band) |
| 17–44 | Soil, Temp, Hum on the left; the animated pot on the right (x 96–127) |
| 48–57 | Health bar, with the % beside it |
| 58–62 | State label in a tiny 3×5 font, right-aligned under the % |

| State | Face | Particles |
|---|---|---|
| Happy | `^ ^` eyes that blink, smile, blush | floating hearts, sparkles, swaying leaves |
| Thirsty | sad eyes, frown, tears | a broken heart that cracks apart, wilted leaves |
| Too hot | `> <` squint, panting | sweat drops, steam |
| Too cold | shivering, chattering teeth | snowflakes |
| Too wet / humid | dizzy X eyes | bubbles, drips |
| Dry air | tired eyes, flat mouth | broken heart, wind, dust |

The sensors are read once per loop. The plant animates 4 times per second inside that loop.

---

## Notifications (ntfy)

1. Install the ntfy app on your phone.
2. Subscribe to your topic name. Use the same `TOPIC` as in `main.py`, and make it hard to guess, because anyone who knows it can read it.
3. That's it. The board POSTs to `http://ntfy.sh/<TOPIC>`.

| Alert | When | Priority |
|---|---|---|
| 💧 Your mint is thirsty | soil too dry | high |
| 🌊 Too much water | soil too wet | default |
| 🔥 Too hot | temperature too high | high |
| ❄️ Too cold | temperature too low | high |
| 🌱 Your mint is happy again | recovered | default |

- It sends as soon as the state changes, then **repeats at most once per hour** (`NOTIFY_EVERY`) while the problem lasts.
- Air problems (dry or humid) show on the screen but **don't** notify, since you can't easily change the air.
- **Plain HTTP is used on purpose.** HTTPS ran the ESP32 out of memory (`ENOMEM`) while the screen was running.

## Sources

- FAO Ecocrop, peppermint (via the Illinois State Water Survey): <https://isws.illinois.edu/data/altcrops/cropreq2.asp?crop=547>
- OMAFRA CropOp, Mint: <https://omafra.gov.on.ca/CropOp/en/herbs/culinary/mint.html>
- Clark, R. J. (1981). *A study of some factors affecting the yield and composition of peppermint oil.* University of Tasmania: <https://figshare.utas.edu.au/articles/thesis/A_study_of_some_factors_affecting_the_yield_and_composition_of_peppermint_oil_mentha_piperita_L_/23235413>
- Runkle, E. *Water Vapor-Pressure Deficit.* Michigan State University: <https://www.canr.msu.edu/floriculture/uploads/files/Water%20VPD.pdf>
- Tucker, A. & Runkle, E. (2025). *The water vapor-pressure deficit regulates growth of culinary herbs and lettuce in controlled environments.* ASHS 2025: <https://ashs2025.sched.com/event/247FJ/ce-2-the-water-vapor-pressure-deficit-regulates-growth-of-culinary-herbs-and-lettuce-in-controlled-environments>
- Water stress in *Mentha piperita* (pot study): <https://dergipark.org.tr/en/pub/mkutbd/article/1792505>
- Peppermint drought stress study (summary): <https://npcvar.idrblab.net/data/naturalproduct/details/NP0385>
