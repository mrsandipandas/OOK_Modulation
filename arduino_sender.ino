// the setup function runs once when you press reset or power the board
String password = "PASS";
String sync_pattern_start = "000101100";
String sync_pattern_end = "00001111";
int signal_time = 100;
int pin_port = 8; 
int heartbeat_port = A0;
int heartbeat_rate = 0;
char inChar;

void setup() {
  // initialize digital pin 8 as an output.
  Serial.begin(9600);
  pinMode(pin_port, OUTPUT);
  digitalWrite(pin_port, LOW);
}

void send_string(String string_data){
  for(int i=0; i< string_data.length(); i++){
    if(string_data[i] == '0')
      digitalWrite(pin_port, HIGH); //This means the transistor has to be on (aka the tag cannot be read)
    else  
      digitalWrite(pin_port, LOW); //This means the transistor has to be off (aka the tag can be read)
    delay(signal_time);
    Serial.println(string_data[i]);
  }
}

// the loop function runs over and over again forever
void loop() {  
  int sensorValue = analogRead(heartbeat_port);
  if (sensorValue > 0 || Serial.available() > 0) {
    inChar = Serial.read();
    heartbeat_rate = readHeartBeat();
    if(heartbeat_rate > 60 || inChar == 'X' ){
      send_string(sync_pattern_start);
      
      for(int i=0; i< password.length(); i++){
        String binary_pattern = String(password[i], BIN);
        while (binary_pattern.length() < 8) {    //pad with 8 0's
          binary_pattern = "0" + binary_pattern;
        }
        //Print the bit for the byte send
        Serial.println(binary_pattern);
        //Here we send the bits
        send_string(binary_pattern);
      }
      send_string(sync_pattern_end);
      digitalWrite(pin_port, LOW); //Transistor off and help to stop
    }
    sensorValue = 0;
    heartbeat_rate = 0;
    inChar = ' ';
  }
}


int readHeartBeat(){
  int rate = 0;
  unsigned long cur_sec = millis();
  while((millis() - cur_sec)<5000){
    int sensorValue = analogRead(heartbeat_port);
    if (sensorValue > 0){
      rate = rate + 1;
    }
    delay(200);
  }
  Serial.println(rate);
  return (12*rate);
}

