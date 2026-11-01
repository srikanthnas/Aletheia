| Strategy   | Distortion      | MIR Recovery   |   Rec. % | Verdict   | Sim (%)   | Hamming   |
|:-----------|:----------------|:---------------|---------:|:----------|:----------|:----------|
| LSB-ADPE   | PNG Save        | Yes            |   100    | verified  | 100.0     | 0         |
| LSB-ADPE   | JPEG 95%        | No             |     0    | FAILED    | -         | -         |
| LSB-ADPE   | JPEG 90%        | No             |     0    | FAILED    | -         | -         |
| LSB-ADPE   | JPEG 80%        | No             |     0    | FAILED    | -         | -         |
| LSB-ADPE   | JPEG 70%        | No             |     0    | FAILED    | -         | -         |
| LSB-ADPE   | Brightness +10% | No             |     0    | FAILED    | -         | -         |
| LSB-ADPE   | Brightness +20% | No             |     0    | FAILED    | -         | -         |
| LSB-ADPE   | Contrast +10%   | No             |     0    | FAILED    | -         | -         |
| LSB-ADPE   | Resize 95%      | No             |     0    | FAILED    | -         | -         |
| LSB-ADPE   | Resize 80%      | No             |     0    | FAILED    | -         | -         |
| LSB-ADPE   | Crop 5%         | No             |     0    | FAILED    | -         | -         |
| LSB-ADPE   | Crop 10%        | No             |     0    | FAILED    | -         | -         |
| LSB-ADPE   | Gaussian Noise  | No             |     0    | FAILED    | -         | -         |
| DCT-QIM    | PNG Save        | Yes            |     6.25 | verified  | 100.0     | 0         |
| DCT-QIM    | JPEG 95%        | Yes            |     6.25 | verified  | 87.5      | 8         |
| DCT-QIM    | JPEG 90%        | Yes            |     6.25 | verified  | 84.38     | 10        |
| DCT-QIM    | JPEG 80%        | Yes            |     6.25 | verified  | 87.5      | 8         |
| DCT-QIM    | JPEG 70%        | Yes            |     6.25 | verified  | 84.38     | 10        |
| DCT-QIM    | Brightness +10% | Yes            |     6.25 | verified  | 84.38     | 10        |
| DCT-QIM    | Brightness +20% | No             |     0    | FAILED    | -         | -         |
| DCT-QIM    | Contrast +10%   | Yes            |     6.25 | verified  | 87.5      | 8         |
| DCT-QIM    | Resize 95%      | No             |     0    | FAILED    | -         | -         |
| DCT-QIM    | Resize 80%      | No             |     0    | FAILED    | -         | -         |
| DCT-QIM    | Crop 5%         | No             |     0    | FAILED    | -         | -         |
| DCT-QIM    | Crop 10%        | No             |     0    | FAILED    | -         | -         |
| DCT-QIM    | Gaussian Noise  | No             |     0    | FAILED    | -         | -         |