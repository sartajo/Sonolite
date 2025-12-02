function [moved] = moveStage(axis,distance,speed)

if (nargin == 2)
    speed = 3;
end;

% moveStage(axis, distance)
%
% Move stage the distance specified (in mm)
%
% axis should be either 'X', 'x' or 'Y', 'y'
%
%if (isvar(Stage)==0)
%config_io;
%end;
%global Stage;
%if(Stage.io.status ~= 0 )
%   error('inp/outp installation failed');
%end
address = hex2dec('d008');

%1600 pulses per revolution;
%mmPerPulse = 5.08/(1600);         % This is based on 0.200" per revolution (imperial)
%PulsePermm = 315;
mmPerPulse = 5.00/1600;             % This is based on 5mm per revolution (metric)
PulsePermm = 320 ;
direction = sign(distance);
distance = abs(distance);
TotalPulsesMoved = 0;

TotalPulses = round(distance*PulsePermm);
runupTime = .05;        			% acceleration time of 0.25 s; 
peakspeed = speed; 				% Peak speed in mm/s (KEEP BELOW 50); was 20 changing to 5 to slow down
a = peakspeed/runupTime;
accelDistance = 0.5*a*runupTime.^2;		% distance needed to accelerate given the acceleration rate, a, above.
AccelPulses = accelDistance*PulsePermm;

PulseRate = peakspeed*PulsePermm;		% Number of pulses per second at peak speed
StepPulse = 1/PulseRate/2;				% Number of seconds per pulse at peak speed.  Each pulse should be half this time.

%TotalPulses
if TotalPulses <(2*AccelPulses) 
  acc = ceil(TotalPulses/2);
  dec = floor(TotalPulses/2);
  accel = linspace(3,1,acc);
  decel = fliplr(linspace(3,1,dec));
else
  acc = ceil(AccelPulses);
  dec = floor(AccelPulses);
  accel = linspace(3,1,acc);
  decel = linspace(1,3,dec);
end;

movePulses = TotalPulses-(acc+dec);
currentPins = inp(address);         % get current pins
enable = bitset(currentPins,8,1);   % set enable LOW
disable = bitset(currentPins,8,0);  % set disable 
outp(address,enable);               % Write enable

currentPins = inp(address);         % Read pins

if (axis == 'X'| axis == 'x')
  if (direction<0)
    currentPins = bitset(currentPins,2,1);
  else
    currentPins = bitset(currentPins,2,0);
  end;
  outp(address,currentPins);  % set direction pin
  currentPins = inp(address);
  pulseOn = bitset(currentPins,1,1);
  pulseOff = bitset(currentPins,1,0);
elseif (axis == 'Y'| axis == 'y')
  if (direction<0)
    currentPins = bitset(currentPins,4,1);
  else
    currentPins = bitset(currentPins,4,0);
  end;
  outp(address,currentPins);  % set direction pin
  currentPins = inp(address);
  pulseOn = bitset(currentPins,3,1);
  pulseOff = bitset(currentPins,3,0);
end;


% Now pulse and move axis
for i = 1:acc
  outp(address,pulseOn);
  t1=tic; while(double(tic-t1)/3e6<(accel(i)*StepPulse)); end;
  outp(address,pulseOff);
  t1 = tic; while(double(tic-t1)/3e6<(accel(i)*StepPulse)); end;
  TotalPulsesMoved = TotalPulsesMoved+1;
end;

for i= 1:movePulses
   outp(address,pulseOn);
   t1 = tic; while(double(tic-t1)/3e6<(StepPulse)); end;
   outp(address,pulseOff);
   t1 = tic; while(double(tic-t1)/3e6<(StepPulse)); end;
   TotalPulsesMoved = TotalPulsesMoved+1;
end;

for i = 1:dec
  outp(address,pulseOn);
  t1=tic; while(double(tic-t1)/3e6<(decel(i)*StepPulse)); end;
  outp(address,pulseOff);
  t1 = tic; while(double(tic-t1)/3e6<(decel(i)*StepPulse)); end;
  TotalPulsesMoved = TotalPulsesMoved+1;
end;

 outp(address,disable);
 %TotalPulsesMoved






