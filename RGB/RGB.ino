#define BLUE 3
#define GREEN 5
#define RED 6

void setup()
{
pinMode(RED, OUTPUT);
pinMode(GREEN, OUTPUT);
pinMode(BLUE, OUTPUT);
digitalWrite(RED, HIGH);
digitalWrite(GREEN, LOW);
digitalWrite(BLUE, LOW);
}

int redValue;
int greenValue;
int blueValue;

void loop()
{
#define delayTime 10 

redValue = 255;
greenValue = 0;
blueValue = 0;

analogWrite(RED, redValue);
analogWrite(GREEN, greenValue);
delay(delayTime);

redValue = 0;
greenValue = 255;
blueValue = 0;

analogWrite(GREEN, greenValue);
analogWrite(BLUE, blueValue);
delay(delayTime);

redValue = 0;
greenValue = 255;
blueValue = 0;

analogWrite(BLUE, blueValue);
analogWrite(RED, redValue);
delay(delayTime);

}
