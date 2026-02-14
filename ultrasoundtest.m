% 1. Read the TXT files into MATLAB
data1 = readmatrix('scan_position_1.txt');
data2 = readmatrix('scan_position_2.txt');

% 2. Extract Channel A (Column 2) and clean out the text headers
wave1 = rmmissing(data1(:, 2));
wave2 = rmmissing(data2(:, 2));

% 3. Process the waves (Absolute value + Envelope)
env1 = envelope(abs(wave1), 50, 'analytic');
env2 = envelope(abs(wave2), 50, 'analytic');

% 4. Match the lengths (TXT files sometimes differ by a few rows)
min_length = min(length(env1), length(env2));
env1 = env1(1:min_length);
env2 = env2(1:min_length);

% 5. Build the Image Matrix!
image_matrix = [env1, env2]; 

% 6. Display the Ultrasound Image
figure;
imagesc(image_matrix);
colormap('gray'); % Make it look like a real medical ultrasound
title('My First B-Scan Image');
ylabel('Depth (Samples)');
xlabel('Scan Position');