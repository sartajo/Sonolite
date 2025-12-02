function [dataout] = Rasterize_PA()
%% ACQUISITION SETUP
%CONNECT

ictObj=icdevice('niscope.mdd','DAQ::Dev2','optionstring','RangeCheck=0');
connect(ictObj);

%SET-UPN
SampleRate = 100e6; %according to PCI-5122 manual, 100MSps 14 bit
RecordTime = 100e-6;
RecordNum = (SampleRate)*(RecordTime);

%autoset DAQ
configuration=ictObj.Configuration;
invoke(configuration,'configureacquisition',0);
%invoke(configuration,'autosetup');
VertRange=2*1;%2*(5.0);
%for Fetching data
acqCh=ictObj.Acquisition;
%acq.Fetch_Relative_To=482; % CHANGED fetch at 1st point sampled by digitizer

%configure Ch0 vertical acq properties (1.5 MHz transducer)
vertCh0=ictObj.vertical;
vertCh0.Channel_Enabled=1; %enable Ch0
vertCh0.Vertical_Range=VertRange; %changed; was 1 before 
vertCh0.Vertical_Coupling=0; %AC Coupling
vertCh0.Vertical_Offset=0;

%configure Ch0
invoke(ictObj.Configurationfunctionsvertical,'configurevertical','0',vertCh0.Vertical_Range,vertCh0.Vertical_Offset,...
    vertCh0.Vertical_Coupling,vertCh0.Probe_Attenuation,true);



pr0=input('Use Channel 1/another transducer? [Y/N] ','s');
if (pr0=='Y') || (pr0=='y')
    Ch1_inp=1;
    %configure Ch1 vertical acq properties (3.5 MHz transducer)
    vertCh1=ictObj.vertical;
    vertCh1.Channel_Enabled=1; %enable Ch1
    vertCh1.Vertical_Range=2*(1.0);
    vertCh1.Vertical_Coupling=0; %AC Coupling
    vertCh0.Vertical_Offset=0;
    %Configure Ch1
    invoke(ictObj.Configurationfunctionsvertical,'configurevertical','1',vertCh1.Vertical_Range,vertCh1.Vertical_Offset,...
        vertCh1.Vertical_Coupling,vertCh1.Probe_Attenuation,true);
elseif (pr0=='N') || (pr0=='n')
    Ch1_inp=0;
end


%configure Ch TRIG properties
Configurationfunctionstrigger = get(ictObj,'Configurationfunctionstrigger');
%TRIG=ictObj.Triggering;
%TRIG.Trigger_Source='VAL_IMMEDIATE';
TRIG.Trigger_Source='VAL_PFI_1';
TRIG.Trigger_Type=1;
TRIG.Trigger_Holdoff=0; %changed from 50us to 0
TRIG.Trigger_Slope=1; %rising edge
TRIG.Trigger_Coupling=0; %AC Coupling
TRIG.Trigger_Level=.50;
TRIG.Trigger_Delay=0;
%invoke(Configurationfunctionstrigger,'configuretriggeredge',TRIG.Trigger_Source,.1,1,0,0,0);
%
invoke(Configurationfunctionstrigger,'configuretriggerdigital',TRIG.Trigger_Source,TRIG.Trigger_Slope,TRIG.Trigger_Holdoff,TRIG.Trigger_Delay)
%invoke(Configurationfunctionstrigger,'configuretriggerdigital',TRIG.Trigger_Source);
%invoke(Configurationfunctionstrigger,'configuretriggeredge',TRIG.Trigger_Source,TRIG.Trigger_Level,TRIG.Trigger_Slope,TRIG.Trigger_Coupling,TRIG.Trigger_Holdoff,TRIG.Trigger_Delay)

%configure Ch0 horizontal acq properties
hor=ictObj.horizontal;
hor.Min_Number_of_Points=RecordNum;
hor.Time_Per_Record=RecordTime;
hor.Enforce_Realtime=1; %changed from both RT+ET to RT only
hor.Acquisition_Start_Time=0; 
%SampleRate = 100e6;
NSamples = RecordNum;
Configurationfunctionshorizontal = get(ictObj,'Configurationfunctionshorizontal');
invoke(Configurationfunctionshorizontal,'configurehorizontaltiming', SampleRate, NSamples,0,1,1);

%configure wfm + wfmInfo array
x_Inc=(RecordTime)/(RecordNum);

wfmInfo.actualSamples=RecordNum;
wfmInfo.absoluteInitialX=0;
wfmInfo.relativeInitialX=0;
wfmInfo.xIncrement=x_Inc;
wfmInfo.offset=0;
wfmInfo.gain=1;

%waveform array --> #of columnss = #of Averages; #of pages = #of posn' of transducer

pr1=input('Number of Averages to be collected? (default=10) ');
if isempty(pr1)
    pr1=10;
end

pr2=input('cm of x-dim? (default=5cm) ');
if isempty(pr2)
    pr2=5;
end
pr3=input('cm of y-dim? (default=5cm) ');
if isempty(pr3)
    pr3=5;
end
pr4=input('Resolution Size of x in cm? (default=0.1cm) ');
if isempty(pr4)
    pr4=0.1;
end
pr5=input('Resolution Size of y in cm? (default=0.1cm) ');
if isempty(pr5)
    pr5=0.1;
end

[b,a] = butter(12,0.05,'low');

YRes=pr4;
XRes=pr5;
Num_of_Averages = pr1;
xnumPosn = pr2/XRes;
ynumPosn = pr3/YRes;

%hor.RIS_Num_Avg=Num_of_Averages;

%wfmCh0=zeros(RecordNum,Num_of_Averages,xnumPosn,ynumPosn);


wfmCh0=zeros(1*int16(RecordNum),Num_of_Averages);
if (pr0=='Y') || (pr0 == 'y')
    wfmCh1=zeros(1*int16(RecordNum),Num_of_Averages);
end


TimeOut=5; %waits idefinitely for samples to become available
wfmx=RecordTime/RecordNum:RecordTime/RecordNum:RecordTime;

disp(RecordNum)
% WRITE FILE 
filename=sprintf('Acq_specs.txt');
fid=fopen(filename,'w');
fprintf(fid,'%d\n',Num_of_Averages);
fprintf(fid,'%0.2f\n',pr2);
fprintf(fid,'%0.2f\n',pr3);
fprintf(fid,'%0.2f\n',YRes);
fprintf(fid,'%0.2f\n',XRes);
fprintf(fid,'%0.2f\n',RecordTime*1e6);
fclose(fid);

%% ACQUIRE
config_io;
xstage=0; ystage=0; 

XPosns = XRes/2:XRes:(abs(pr2)-XRes/2);
YPosns = YRes/2:YRes:(abs(pr3)-YRes/2);

XP = abs(XPosns);
XIndex = 1;
YP = abs(YPosns);
YIndex = 1;
XInc = 1;
YInc = 1;
if (pr2<0) 
  XPosns = fliplr(XPosns);
  XRes = -XRes;
  XIndex = length(XPosns);
  XInc = -XInc;
end;
if (pr3<0)
  YPosns = fliplr(YPosns);
  YRes = -YRes;
  YIndex = length(YPosns);
  YInc = -YInc;
end;
if (pr3==0)
  YPosns = 1;
  YIndex = length(YPosns);
end;

CurrentPosn = [XPosns(1) YPosns(1)];
counterY = 1;

dataout_Ch0 = zeros(length(XPosns),length(YPosns),int16(RecordNum),Num_of_Averages,'int16');

if (Ch1_inp)
   dataout_Ch1 = zeros(length(XPosns),length(YPosns),int16(RecordNum),Num_of_Averages,'int16');
end;
img_out = zeros(length(YPosns),length(XPosns));

for y=1:length(YPosns)
  counterX = 1;
  for x=1:length(XPosns)
      pause(0.2)
    for k=1:Num_of_Averages
        if ~(Ch1_inp) 
          acquisition = get(ictObj,'Acquisition');
          invoke(acquisition,'initiateacquisition');
          [wfmCh0(:,k) wfminfo] = invoke(acquisition,'fetchbinary16','0',TimeOut,RecordNum,wfmCh0(:,k),wfmInfo);
%        [wfmCh0(:,k),wfmInfo]=invoke(acqCh,'read','0',TimeOut,RecordNum,wfmCh0(:,k),wfmInfo); %every other empty pixel error fixed!!
 %wfmCh0(:,k) = CurrentPosn(1)*ones(RecordNum,1,'int16');
        %pause(.1);
        else
            acquisition = get(ictObj,'Acquisition');
          % disp([x k]);
          invoke(acquisition,'initiateacquisition');
  %          wfmCh1(:,k) = CurrentPosn(2)*ones(1,RecordNum,'int16');
            [wfmCh0(:,k) wfminfo] = invoke(acquisition,'fetchbinary16','0',TimeOut,RecordNum,wfmCh0(:,k),wfmInfo);
            [wfmCh1(:,k) wfminfo] = invoke(acquisition,'fetchbinary16','1',TimeOut,RecordNum,wfmCh1(:,k),wfmInfo);
  %         [wfmCh1(:,k),wfmInfo]=invoke(acqCh,'read','1',TimeOut,RecordNum,wfmCh1(:,k),wfmInfo);
        end    
        
    end
    
    %xx = find(XP==CurrentPosn(1));
    %yy = find(YP==CurrentPosn(2));
    
    xx = XIndex;
    yy = YIndex;
        
    disp(sprintf('[%d %d] -> [%d %d %d]\n',CurrentPosn(1), CurrentPosn(2), xx, yy, XInc));

    dataout_Ch0(xx,yy,:,:) = reshape(wfmCh0,1,1,int16(RecordNum),Num_of_Averages);
    %dataout_Ch0(xx,yy,:,:) = filtfilt(b,a,wfmCh0);
    if (Ch1_inp)
        dataout_Ch1(xx,yy,:,:) = reshape(wfmCh1,1,1,int16(RecordNum),Num_of_Averages);
    end;
%    arrname=strcat('Ch0_R',int2str(xx),'C',int2str(yy),'.mat');
%    save(arrname,'wfmCh0');
%    clear wfmCh0;
%    wfmCh0=zeros(1*int16(RecordNum),Num_of_Averages);
    
%    if(Ch1_inp)
%        arrname=strcat('Ch1_R',int2str(x),'C',int2str(y),'.mat');
%        save(arrname,'wfmCh1');
%        clear wfmCh1;
%        wfmCh1=zeros(1*int16(RecordNum),Num_of_Averages);plot(d
%    end 
  img_out(length(YPosns)+1-yy,xx) = sum(sum(abs(dataout_Ch0(xx,yy,500:3000,:)),4),3);
  imagesc(img_out); drawnow;
    if (x <= (length(XPosns)-1))
      moveStage('x',XRes*10);
      CurrentPosn(1) = CurrentPosn(1)+XRes;
    else
      CurrentPosn(1) = CurrentPosn(1);
      XIndex = XIndex+XInc;
      XInc = -XInc;
    end;
    XIndex = XIndex+XInc;
  end;
  XRes = -XRes;

  if (y <= length(YPosns)-1)

      moveStage('y',YRes*10);
      CurrentPosn(2) = CurrentPosn(2)+YRes;
    else
       CurrentPosn(2) = CurrentPosn(2);
       YIndex = YIndex+YInc;
       YInc = -YInc;
    end;
    YIndex = YIndex+YInc;
    %disp(CurrentPosn);
end;

%% DISCONNECT
disconnect(ictObj);
delete(ictObj);
clear ictObj;
%clear all; 
%end

dataout(:,:,:,:,1) = dataout_Ch0;
if (Ch1_inp)
    dataout(:,:,:,:,2) = dataout_Ch1;
end;

% Zayeed's edits
v_water = 1481; % m/s
v_plexi = 2750; % m/s
Ts = 10e-9; % 10 ns
time = 0:Ts:Ts*(10000-1);
distance_mm = time*v_water*1000/2 % mm;

dataout2 = mean(dataout,4);
figure;
xlabel("s");
ylabel("Amplitude mV");
title("Graph 1: 1 pixel Echo");
plot(squeeze(dataout2(1,1,:)))
figure;
xlabel("s");
ylabel("Amplitude mV");
title("Graph 2: 1 pixel Echo");
plot(squeeze(dataout2(5,1,:)))
figure;
imagesc(squeeze(abs(dataout2(:,:,1:6000)))');

figure;
xlabel("mm");
ylabel("Amplitude mV");
title("Graph 3: 1 pixel Echo w/ distance");
plot(distance_mm, squeeze(dataout2(1,1,:)));

figure;
imagesc(distance_mm, squeeze(abs(dataout2(:,:,1:6000)))');

%home back
XMove = -(CurrentPosn(1)-XPosns(1));
YMove = -(CurrentPosn(2)-YPosns(1));
moveStage('x',XMove*10);
moveStage('y',YMove*10);