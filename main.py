from machine import Pin, ADC, SoftI2C
import time
import dht
import framebuf
import math
import network
import requests

# ---------- OLED driver (SSD1306) ----------
class SSD1306_I2C(framebuf.FrameBuffer):
    def __init__(self, width, height, i2c, addr=0x3C):
        self.width, self.height, self.i2c, self.addr = width, height, i2c, addr
        self.pages = height // 8
        self.buffer = bytearray(self.pages * width)
        super().__init__(self.buffer, width, height, framebuf.MONO_VLSB)
        for c in (0xAE, 0x20, 0x00, 0x40, 0xA1, 0xA8, height - 1, 0xC8,
                  0xD3, 0x00, 0xDA, 0x12, 0xD5, 0x80, 0xD9, 0xF1,
                  0xDB, 0x30, 0x81, 0xFF, 0xA4, 0xA6, 0x8D, 0x14, 0xAF):
            self.write_cmd(c)

    def write_cmd(self, c):
        self.i2c.writeto(self.addr, bytes((0x80, c)))

    def show(self):
        for c in (0x21, 0, self.width - 1, 0x22, 0, self.pages - 1):
            self.write_cmd(c)
        self.i2c.writeto(self.addr, b"\x40" + self.buffer)

# ---------- Sensors ----------

soil = ADC(Pin(35))  # capacitive soil sensor
soil.atten(ADC.ATTN_11DB)

sensor = dht.DHT11(Pin(25))  # DHT11 temp and humidity sensor

i2c = SoftI2C(sda=Pin(32), scl=Pin(33))  # OLED bus
oled = SSD1306_I2C(128, 64, i2c)  # 128x64 screen

# ---------- WiFi + ntfy notifications ----------
WIFI_NAME = "your-wifi-name"     # 2.4 GHz network only (ESP32 has no 5 GHz)
WIFI_PASS = "your-wifi-password"
TOPIC = "your-random-topic"   # same topic as in the ntfy app - make it hard to guess
NOTIFY_EVERY = 3600           # repeat a warning at most once per hour (seconds)

wifi = network.WLAN(network.STA_IF)
wifi.active(True)

def wifi_connect():
    if wifi.isconnected():
        return True
    wifi.connect(WIFI_NAME, WIFI_PASS)
    for _ in range(20):          # wait up to 10 s
        if wifi.isconnected():
            return True
        time.sleep(0.5)
    return False

def notify(title, text, tags, priority="default"):
    try:
        if wifi_connect():
            r = requests.post("http://ntfy.sh/" + TOPIC,
                              data=text.encode(),
                              headers={"Title": title, "Tags": tags, "Priority": priority})
            r.close()
            print("ntfy sent:", title)
    except Exception as e:
        print("ntfy failed:", e)   # no WiFi etc. - keep the plant running

ALERTS = {   # title, message, emoji tag, priority
    "thirsty": ("Your mint is thirsty", "Soil {:.0f}%. Time to water!", "droplet", "high"),
    "wet":     ("Too much water",       "Soil {:.0f}%. Let it dry out.", "ocean", "default"),
    "hot":     ("Too hot",              "{} C. Move it somewhere cooler.", "fire", "high"),
    "cold":    ("Too cold",             "{} C. Move it somewhere warmer.", "snowflake", "high"),
}

wifi_connect()

# ---------- Health score System (Excel) ----------

def vpd(t, h):
    es = 0.6108 * math.exp(17.27 * t / (t + 237.3))   # max water air can hold (kPa)
    return es * (1 - h / 100)                         # how much it's missing

def get_scores(pct, t, h):
    v = vpd(t, h)
    temp_score = max(0, min(1, 0.0909 * t - 0.3636, -0.1 * t + 3.5))
    hum_score  = max(0, min(1, 2.5 * v - 0.75,      -1.0 * v + 2.5))
    soil_score = max(0, min(1, 0.0588 * pct - 0.5294, -0.1 * pct + 4.5))
    return temp_score, hum_score, soil_score

def health(temp_score, hum_score, soil_score):
    return (temp_score + hum_score + soil_score) / 3 * 100   # 0-100 %

def state(pct, t, h, temp_score, hum_score, soil_score):
    worst = min(temp_score, hum_score, soil_score)   # what's dragging the average down
    if worst >= 0.5:
        return "happy"
    if worst == soil_score:
        return "thirsty" if pct < 26 else "wet"
    if worst == temp_score:
        return "hot" if t > 25 else "cold"
    return "dry" if vpd(t, h) > 1.5 else "humid"


# ---------- Animation ----------
HEART  = ("01010", "11111", "01110", "00100")          # small 5x4
BIG    = ("0110110", "1111111", "1111111", "0111110", "0011100", "0001000")  # 7x6

def bitmap(rows, x, y, c=1):
    for j, row in enumerate(rows):
        for i, b in enumerate(row):
            if b == "1":
                oled.pixel(x + i, y + j, c)

def broken_heart(x, y, gap):
    # 7x6 heart cracked down the middle; halves drift apart, a shard falls
    for j, row in enumerate(BIG):
        cut = 3 if j % 2 == 0 else 2
        for i, b in enumerate(row):
            if b == "1" and i != cut:
                oled.pixel(x + i + (-gap if i < cut else gap), y + j, 1)
    if gap:
        oled.pixel(x + 3, y + 7 + gap, 1)

def sparkle(x, y):
    oled.pixel(x, y, 1); oled.pixel(x - 1, y, 1); oled.pixel(x + 1, y, 1)
    oled.pixel(x, y - 1, 1); oled.pixel(x, y + 1, 1)

def pot(j=0):
    oled.fill_rect(99 + j, 28, 26, 3, 1)      # rim
    oled.fill_rect(101 + j, 31, 22, 14, 1)    # pot = face

def sprout(s, j=0):
    oled.line(112 + j, 28, 112 + j + s // 2, 21, 1)
    oled.ellipse(107 + j + s, 23, 4, 2, 1, True)
    oled.ellipse(117 + j + s, 21, 4, 2, 1, True)

def wilted(d):
    oled.line(112, 28, 113, 24, 1); oled.line(113, 24, 117, 23 + d, 1)
    oled.ellipse(118, 24 + d, 2, 2, 1, True)
    oled.line(112, 26, 106, 27 + d, 1)

def blush(j=0):
    for x in (103, 119):
        oled.pixel(x + j, 40, 0); oled.pixel(x + j + 2, 40, 0); oled.pixel(x + j + 1, 41, 0)

def draw_happy(f):
    s = (0, 1, 2, 1, 0, -1, -2, -1)[f % 8]
    pot(); sprout(s)
    if f % 10 == 0:                                   # blink
        oled.hline(105, 36, 4, 0); oled.hline(115, 36, 4, 0)
    else:                                             # ^ ^ happy eyes
        for cx in (107, 117):
            oled.pixel(cx - 2, 37, 0); oled.pixel(cx - 1, 36, 0); oled.pixel(cx, 35, 0)
            oled.pixel(cx + 1, 36, 0); oled.pixel(cx + 2, 37, 0)
    for x, y in ((108, 40), (109, 41), (110, 42), (111, 42), (112, 42), (113, 42), (114, 41), (115, 40)):
        oled.pixel(x, y, 0)                           # big smile
    blush()
    for k, (x0, off) in enumerate(((96, 0), (123, 5))):  # hearts floating up
        y = 24 - (f + off) % 8
        bitmap(HEART, x0 + (f // 2 + k) % 2, y)
    sparkle(101, 18) if f % 4 < 2 else sparkle(126, 27)

def draw_thirsty(f):
    d = (0, 1, 1, 0)[f % 4]
    pot(); wilted(d)
    for cx in (107, 117):                             # sad eyes + brows
        oled.fill_rect(cx - 1, 36, 2, 2, 0)
    oled.line(104, 35, 107, 34, 0); oled.line(120, 35, 117, 34, 0)
    oled.line(109, 42, 112, 40, 0); oled.line(112, 40, 115, 42, 0)   # frown
    ty = 38 + f % 6                                   # tears running down
    oled.vline(106, 38, min(ty, 44) - 37, 0); oled.vline(119, 38, min(ty, 44) - 37, 0)
    broken_heart(97, 18, (0, 0, 1, 1, 1, 0)[f % 6])

def draw_hot(f):
    pot(); sprout(0)
    for cx in (107, 117):                             # > < squint
        oled.line(cx - 2, 34, cx, 36, 0); oled.line(cx, 36, cx - 2, 38, 0)
    oled.fill_rect(110, 40, 5, 2 + f % 2, 0)          # panting mouth
    blush()
    for k, x in enumerate((97, 126)):                 # sweat sliding down the sides
        y = 30 + (f * 2 + k * 5) % 14
        oled.ellipse(x, y, 1, 2, 1, True)
    for k, x0 in enumerate((101, 121)):               # steam rising
        y = 25 - (f + k * 3) % 8
        oled.pixel(x0 + (y % 2), y, 1); oled.pixel(x0 + 1 - (y % 2), y - 1, 1)

def draw_cold(f):
    j = (-1, 1)[f % 2]                                # shiver
    pot(j); sprout(0, j)
    oled.fill_rect(106 + j, 35, 2, 3, 0); oled.fill_rect(116 + j, 35, 2, 3, 0)
    for i in range(5):                                # chattering teeth
        oled.pixel(108 + j + 2 * i, 40 + (i + f) % 2, 0)
        oled.pixel(109 + j + 2 * i, 40 + (i + f + 1) % 2, 0)
    for x, off in ((98, 0), (104, 7), (120, 3), (126, 10)):   # snowflakes
        sparkle(x, 18 + (f * 2 + off) % 14)

def draw_wet(f):
    pot(); sprout(0)
    for cx in (107, 117):                             # dizzy X eyes
        oled.line(cx - 1, 34, cx + 1, 36, 0); oled.line(cx - 1, 36, cx + 1, 34, 0)
    for i in range(4):                                # wobbly mouth
        oled.pixel(109 + 2 * i, 40 + (i + f) % 2, 0); oled.pixel(110 + 2 * i, 40 + (i + f + 1) % 2, 0)
    for x, off in ((98, 0), (125, 4)):                # bubbles rising
        y = 25 - (f + off) % 8
        oled.ellipse(x, y, 2, 2, 1)
    for x, off in ((104, 2), (120, 8)):               # drips
        oled.vline(x, 17 + (f * 3 + off) % 8, 2, 1)

def draw_dry(f):
    pot(); sprout((0, 1)[f % 2])
    oled.hline(105, 36, 4, 0); oled.hline(115, 36, 4, 0)      # tired eyes
    oled.pixel(105, 35, 0); oled.pixel(118, 35, 0)
    oled.hline(109, 41, 6, 0)                                  # flat mouth
    broken_heart(97, 18, (0, 1, 1, 0)[f % 4])
    for i, y in enumerate((20, 25)):                           # dry wind
        x = 112 + (f * 2 + 5 * i) % 12
        oled.line(x, y, x + 2, y - 1, 1); oled.line(x + 2, y - 1, x + 4, y, 1)
    oled.pixel(96 + (f * 3) % 30, 44 - f % 3, 1)               # dust, x + 4, y, 1)
 
ANIM = {"happy": draw_happy, "thirsty": draw_thirsty, "hot": draw_hot,
        "wet": draw_wet, "cold": draw_cold, "dry": draw_dry,
        "humid": draw_wet}
 
LABELS = {"happy": "Happy", "thirsty": "Thirsty", "hot": "Too hot",
          "wet": "Too wet", "cold": "Too cold", "dry": "Dry air",
          "humid": "Too humid"}

# ---------- Tiny 3x5 font (for the state label) ----------
TINY = {
    "A": "010101111101101", "C": "011100100100011", "D": "110101101101110",
    "E": "111100110100111", "H": "101101111101101", "I": "111010010010111",
    "L": "100100100100111", "M": "101111111101101", "O": "010101101101010",
    "P": "110101110100100", "R": "110101110101101", "S": "011100010001110",
    "T": "111010010010010", "U": "101101101101111", "W": "101101111111101",
    "Y": "101101010010010", " ": "000000000000000",
}

def small_text(text, x, y):
    for ch in text.upper():
        bits = TINY.get(ch, TINY[" "])
        for i in range(15):
            if bits[i] == "1":
                oled.pixel(x + i % 3, y + i // 3, 1)
        x += 4   # 3 px letter + 1 px gap

last_alert = "happy"
last_alert_time = -NOTIFY_EVERY

# ---------- Loop ----------

while True:
    v = soil.read_uv() / 1e6
    pct = (0.8594 - 0.3243 * v) * 100
    pct = max(0, pct)  # dry soil reads above the calibrated range, so the minimum is set to zero to avoid negative readings.

    try:
        sensor.measure()
        t = sensor.temperature()
        h = sensor.humidity()
    except OSError:
        time.sleep(1)
        continue   # bad DHT11 read, try again
    s = get_scores(pct, t, h)
    health_pct = int(health(*s))
    st = state(pct, t, h, *s)
    frame = time.time()
    print("Soil: {:.1f} %  Temp: {} C  Hum: {} %".format(pct, t, h))

    # ---------- notifications ----------
    now = time.time()
    alert = st if st in ALERTS else "happy"   # air problems: no notification
    if alert != last_alert or (alert != "happy" and now - last_alert_time > NOTIFY_EVERY):
        if alert == "happy":
            if last_alert != "happy":
                notify("Your mint is happy again", "Health {}%".format(health_pct), "seedling")
        else:
            title, msg, tag, prio = ALERTS[alert]
            value = pct if alert in ("thirsty", "wet") else t
            notify(title, msg.format(value) + " Health {}%.".format(health_pct), tag, prio)
        last_alert = alert
        last_alert_time = now
        
# ---------- Oled screen graphics ----------

    oled.fill(0)

    # title (y 0-10)
    oled.text("Plant Health", 16, 1)
    oled.hline(0, 10, 128, 1)

    # readings (left side, y 14-43)
    oled.text("Soil {:.0f}%".format(pct), 0, 17)
    oled.text("Temp {}C".format(t), 0, 27)
    oled.text("Hum  {}%".format(h), 0, 37)

    # plant (right side, x 96-127, y 11-41)
    ANIM[st](frame)

    # health bar (y 48-57)
    oled.rect(0, 48, 90, 10, 1)
    oled.fill_rect(2, 50, 86 * health_pct // 100, 6, 1)

    # percentage + small state label underneath, right-aligned
    p = "{}%".format(health_pct)
    oled.text(p, 128 - 8 * len(p), 47)
    label = LABELS[st]
    small_text(label, 128 - (4 * len(label) - 1), 58)

    oled.show()

    # animate the plant 4 times per second
    for _ in range(4):
        oled.fill_rect(96, 16, 32, 30, 0)   # clear only the plant area
        ANIM[st](frame)
        oled.show()
        frame += 1
        time.sleep(0.25)
