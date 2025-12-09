int switchPin = 12;
int LEDPin   = 4;
int lastState = -1;

void setup() {
  pinMode(switchPin, INPUT);
  pinMode(LEDPin, OUTPUT);

  Serial.begin(9600);
}

void loop() {
  int state = digitalRead(switchPin);
  digitalWrite(LEDPin, state);

  if (state != lastState) {
    Serial.print("Switch state: ");
    Serial.println(state);
    lastState = state;
  }

}
