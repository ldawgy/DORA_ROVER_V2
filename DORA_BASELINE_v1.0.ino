// =====================================================
// 🧭 DORA BASELINE v1.0 — GROUND-TRUTH MECANUM FIRMWARE
// Teensy + L298N (Burst-PWM Safe)
// -----------------------------------------------------
// Coordinate frame:
//   +X → clockwise rotation
//   +Y → forward
//   +R → right strafe
// Verified wiring (matches ULTRACLEAN spin test):
//   FL = FRONT_IN1, FRONT_IN2, FRONT_ENA
//   FR = FRONT_IN3, FRONT_IN4, FRONT_ENB
//   BL = BACK_IN3,  BACK_IN4,  BACK_ENB
//   BR = BACK_IN1,  BACK_IN2,  BACK_ENA
// =====================================================

#include <Servo.h>

// ---------- Motor driver pins ----------
#define BACK_ENA 0
#define BACK_IN1 1
#define BACK_IN2 2
#define BACK_IN3 3
#define BACK_IN4 4
#define BACK_ENB 5

#define FRONT_ENA 7
#define FRONT_IN1 8
#define FRONT_IN2 9
#define FRONT_IN3 10
#define FRONT_IN4 11
#define FRONT_ENB 12

// ---------- Burst struct ----------
struct Burst {
  int in1 = 0, in2 = 0;
  int dir = 0;
  uint16_t onMs = 0;
  bool active = false;
};

Burst bFL, bFR, bBL, bBR;

// ---------- Burst timing ----------
const uint16_t FRAME_MS   = 50;
const uint16_t MIN_ON_MS  = 15;
const uint16_t DEAD_MS    = 0;

// ---------- Speed shaping ----------
double slowMo = 80;     // global throttle %
int deadBand  = 35;

// ---------- Control globals ----------
const unsigned long timeoutMs = 800;
unsigned long lastCommandTime = 0;
const int SLEW_STEP = 30;
int tgtX=0,tgtY=0,tgtR=0, curX=0,curY=0,curR=0;
unsigned long frameStart = 0;

// ---------- Command buffer ----------
const unsigned long CMD_BUFFER_MS = 300;
unsigned long lastCmdBuffer = 0;

// ---------- Function declarations ----------
void handleCommand(const String& c);
bool parseVelocity(const String& s);
int slew(int cur,int tgt,int step);
void setTargets(int x,int y,int r);
void startBurst(int in1,int in2,int cmd);
void updateBurst(int in1,int in2);
Burst* mapBurstPins(int in1,int in2);
void updateBurstOne(Burst* b);

// =====================================================
// SETUP
// =====================================================
void setup() {
  Serial.begin(9600);
  Serial.println("🟢 DORA BASELINE v1.0 — READY");

  int pins[] = {
    BACK_ENA, BACK_ENB, BACK_IN1, BACK_IN2, BACK_IN3, BACK_IN4,
    FRONT_ENA, FRONT_ENB, FRONT_IN1, FRONT_IN2, FRONT_IN3, FRONT_IN4
  };
  for (int i=0;i<12;i++) pinMode(pins[i], OUTPUT);

  analogWrite(BACK_ENA, 255);
  analogWrite(BACK_ENB, 255);
  analogWrite(FRONT_ENA, 255);
  analogWrite(FRONT_ENB, 255);

  frameStart = millis();
}

// =====================================================
// MAIN LOOP
// =====================================================
void loop() {
  // ---- read from GUI / serial ----
  if (Serial.available() > 0) {
    String s = Serial.readStringUntil('\n'); s.trim();
    if (s.length()) {
      if (!parseVelocity(s)) handleCommand(s);
      lastCommandTime = millis();
    }
  }

  // ---- watchdog ----
  if (millis() - lastCommandTime > timeoutMs)
    tgtX = tgtY = tgtR = 0;

  // ---- drive frame ----
  if (millis() - frameStart >= FRAME_MS) {
    frameStart += FRAME_MS;

    curX = slew(curX, tgtX, SLEW_STEP);
    curY = slew(curY, tgtY, SLEW_STEP);
    curR = slew(curR, tgtR, SLEW_STEP);

    // =====================================================
    // ✅ Canonical Mecanum Kinematics (ROS-aligned)
    // =====================================================
    int mFL =  curY + curX + curR;
    int mFR =  curY - curX - curR;
    int mBL =  curY - curX + curR;
    int mBR =  curY + curX - curR;

    // Optional polarity fix — uncomment ONLY if one wheel spins wrong
    // mFL = -mFL;

    // normalize
    int maxMag = max(max(abs(mFL),abs(mFR)), max(abs(mBL),abs(mBR)));
    if (maxMag > 255) {
      mFL = mFL * 255 / maxMag;
      mFR = mFR * 255 / maxMag;
      mBL = mBL * 255 / maxMag;
      mBR = mBR * 255 / maxMag;
    }

    // =====================================================
    // ✅ Pin mapping (matches ULTRACLEAN spin test)
    // =====================================================
    startBurst(FRONT_IN1, FRONT_IN2, mFL);  // Front-Left
    startBurst(FRONT_IN3, FRONT_IN4, mFR);  // Front-Right
    startBurst(BACK_IN3,  BACK_IN4,  mBL);  // Back-Left
    startBurst(BACK_IN1,  BACK_IN2,  mBR);  // Back-Right
  }

  // ---- update bursts ----
  updateBurst(FRONT_IN1, FRONT_IN2);
  updateBurst(FRONT_IN3, FRONT_IN4);
  updateBurst(BACK_IN3,  BACK_IN4);
  updateBurst(BACK_IN1,  BACK_IN2);
}

// =====================================================
// COMMAND HANDLING
// =====================================================
void handleCommand(const String& c){
  unsigned long now = millis();
  if (now - lastCmdBuffer < CMD_BUFFER_MS) return;
  lastCmdBuffer = now;

  // Canonical command → axis map
  if (c=="F")      setTargets(0, 255, 0);   // forward
  else if (c=="B") setTargets(0,-255, 0);   // backward
  else if (c=="L") setTargets(-255, 0, 0);  // strafe left
  else if (c=="R") setTargets( 255, 0, 0);  // strafe right
  else if (c=="CW")  setTargets(0,0, 255);  // rotate clockwise
  else if (c=="CCW") setTargets(0,0,-255);  // rotate counter-clockwise
  else if (c=="S")   setTargets(0,0,0);     // stop
}

// =====================================================
// VELOCITY PARSER
// =====================================================
bool parseVelocity(const String& s){
  int vx,vy,w;
  if (sscanf(s.c_str(),"VX:%d,VY:%d,W:%d",&vx,&vy,&w)==3){
    vx = constrain(vx,-255,255);
    vy = constrain(vy,-255,255);
    w  = constrain(w, -255,255);
    setTargets(vx,vy,w);
    return true;
  }
  return false;
}

// =====================================================
// HELPERS
// =====================================================
void setTargets(int x,int y,int r){ tgtX=x; tgtY=y; tgtR=r; }

int slew(int cur,int tgt,int step){
  if (tgt>cur) return cur + min(step, tgt-cur);
  if (tgt<cur) return cur - min(step, cur-tgt);
  return cur;
}

// =====================================================
// BURST-PWM MACHINERY
// =====================================================
Burst* mapBurstPins(int in1,int in2){
  if (in1==FRONT_IN1) return &bFL;
  if (in1==FRONT_IN3) return &bFR;
  if (in1==BACK_IN3)  return &bBL;
  return &bBR;
}

void startBurst(int in1,int in2,int cmd){
  Burst* b = mapBurstPins(in1,in2);
  b->in1 = in1; b->in2 = in2;

  if (abs(cmd) <= deadBand){
    b->dir = 0; b->onMs = 0; b->active = true;
    return;
  }

  b->dir = (cmd>0) ? 1 : -1;
  float duty = (float)abs(cmd) / 255.0f;
  duty *= (slowMo/100.0f);

  uint16_t on = (uint16_t)(duty * FRAME_MS);
  if (on>0 && on < MIN_ON_MS) on = MIN_ON_MS;
  if (on > FRAME_MS - DEAD_MS) on = FRAME_MS - DEAD_MS;

  b->onMs = on;
  b->active = true;
}

void updateBurstOne(Burst* b){
  if (!b->active) return;
  unsigned long t = millis() - frameStart;
  bool on = (t < b->onMs);

  if (b->dir == 0 || b->onMs==0){
    digitalWrite(b->in1, LOW);
    digitalWrite(b->in2, LOW);
    return;
  }

  if (on){
    if (b->dir > 0){
      digitalWrite(b->in1, HIGH);
      digitalWrite(b->in2, LOW);
    }else{
      digitalWrite(b->in1, LOW);
      digitalWrite(b->in2, HIGH);
    }
  }else{
    digitalWrite(b->in1, LOW);
    digitalWrite(b->in2, LOW);
  }
}

void updateBurst(int in1,int in2){
  updateBurstOne(mapBurstPins(in1,in2));
}

