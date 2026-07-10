# Data Compare Report

## Athlete: athlete_001

- runs: rows existing=856, temp=856; cols existing=101, temp=101

  - cols only in existing: ['activityId', 'deviceId']

  - cols only in temp: ['activity_id', 'device_id']

  - date_range existing=('2016-11-13', '2026-05-07'), temp=('2016-11-13', '2026-05-07')

- metrics: rows existing=693, temp=165; cols existing=13, temp=37

  - cols only in existing: ['calendarDate', 'deviceId', 'userProfilePK']

  - cols only in temp: ['createTimestampUTC', 'device_id', 'firstbeatRunningLtTimestamp', 'functionalThresholdPower', 'height', 'lactateThresholdHearRate', 'lactateThresholdHeartRate', 'lactateThresholdSpeed', 'metaData', 'metrics']...

  - date_range existing=('2024-06-19', '2026-05-12'), temp=('1970-01-01', '2026-04-27')

- predictions: rows existing=693, temp=693; cols existing=15, temp=14

  - cols only in existing: ['calendarDate', 'deviceId', 'raceTime10K', 'raceTime5K', 'raceTimeHalf', 'raceTimeMarathon', 'userProfilePK']

  - cols only in temp: ['device_id', 'race_time_10k', 'race_time_5k', 'race_time_half', 'race_time_marathon', 'user_id']

  - date_range existing=('2024-06-19', '2026-05-12'), temp=('2024-06-19', '2026-05-12')

- readiness: rows existing=1537, temp=1537; cols existing=31, temp=30

  - cols only in existing: ['calendarDate', 'deviceId', 'timestampLocal', 'userProfilePK']

  - cols only in temp: ['device_id', 'timestamp_local', 'user_id']

  - date_range existing=('2024-07-16', '2026-05-12'), temp=('2024-07-16', '2026-05-12')

- maxmet: rows existing=686, temp=686; cols existing=16, temp=15

  - cols only in existing: ['calendarDate', 'deviceId', 'maxMet', 'userProfilePK', 'vo2MaxValue']

  - cols only in temp: ['device_id', 'max_met', 'user_id', 'vo2max']

  - date_range existing=('2021-07-08', '2026-05-07'), temp=('2021-07-08', '2026-05-07')

- history: rows existing=2725, temp=2725; cols existing=16, temp=15

  - cols only in existing: ['calendarDate', 'deviceId', 'userProfilePK']

  - cols only in temp: ['device_id', 'user_id']

  - date_range existing=('2021-07-14', '2026-05-12'), temp=('2021-07-14', '2026-05-12')

- daily_master: rows existing=682, temp=682; cols existing=50, temp=47

  - cols only in existing: ['maxMet', 'run_count', 'vo2MaxValue']

  - date_range existing=('2016-11-13', '2026-05-07'), temp=('2016-11-13', '2026-05-07')



## Athlete: athlete_002

- runs: rows existing=2645, temp=2645; cols existing=91, temp=91

  - cols only in existing: ['activityId', 'deviceId']

  - cols only in temp: ['activity_id', 'device_id']

  - date_range existing=('2015-11-22', '2026-06-26'), temp=('2015-11-22', '2026-06-26')

- metrics: rows existing=1839, temp=1840; cols existing=18, temp=35

  - cols only in existing: ['calendarDate', 'deviceId', 'userProfilePK']

  - cols only in temp: ['activityClass', 'device_id', 'functionalThresholdPower', 'height', 'metaData', 'sportId', 'userSetNullForActivityClass', 'userSetNullForHeight', 'userSetNullForLactateThresholdHR', 'userSetNullForLactateThresholdRowingHR']...

  - date_range existing=('2021-05-25', '2026-06-29'), temp=('2021-05-25', '2026-06-29')

- predictions: rows existing=1848, temp=1848; cols existing=15, temp=14

  - cols only in existing: ['calendarDate', 'deviceId', 'raceTime10K', 'raceTime5K', 'raceTimeHalf', 'raceTimeMarathon', 'userProfilePK']

  - cols only in temp: ['device_id', 'race_time_10k', 'race_time_5k', 'race_time_half', 'race_time_marathon', 'user_id']

  - date_range existing=('2021-05-25', '2026-06-29'), temp=('2021-05-25', '2026-06-29')

- readiness: missing in both

- maxmet: rows existing=1706, temp=1706; cols existing=16, temp=15

  - cols only in existing: ['calendarDate', 'deviceId', 'maxMet', 'userProfilePK', 'vo2MaxValue']

  - cols only in temp: ['device_id', 'max_met', 'user_id', 'vo2max']

  - date_range existing=('2019-06-25', '2026-06-26'), temp=('2019-06-25', '2026-06-26')

- history: rows existing=5634, temp=5634; cols existing=16, temp=15

  - cols only in existing: ['calendarDate', 'deviceId', 'userProfilePK']

  - cols only in temp: ['device_id', 'user_id']

  - date_range existing=('2019-06-18', '2026-06-29'), temp=('2019-06-18', '2026-06-29')

- daily_master: rows existing=2158, temp=2158; cols existing=34, temp=31

  - cols only in existing: ['maxMet', 'run_count', 'vo2MaxValue']

  - date_range existing=('2015-11-22', '2026-06-26'), temp=('2015-11-22', '2026-06-26')



## Athlete: athlete_003

- runs: rows existing=1324, temp=1324; cols existing=122, temp=122

  - cols only in existing: ['activityId', 'deviceId']

  - cols only in temp: ['activity_id', 'device_id']

  - date_range existing=('2018-06-11', '2026-06-29'), temp=('2018-06-11', '2026-06-29')

- metrics: rows existing=1421, temp=393; cols existing=27, temp=53

  - cols only in existing: ['calendarDate', 'deviceId', 'userProfilePK']

  - cols only in temp: ['activityClass', 'createTimestampUTC', 'device_id', 'firstbeatRunningLtTimestamp', 'ftpAutoDetected', 'functionalThresholdPower', 'height', 'lactateThresholdHearRate', 'lactateThresholdHeartRate', 'lactateThresholdSpeed']...

  - date_range existing=('2022-08-09', '2026-06-29'), temp=('1970-01-01', '2026-06-29')

- predictions: rows existing=1449, temp=1450; cols existing=15, temp=22

  - cols only in existing: ['calendarDate', 'deviceId', 'raceTime10K', 'raceTime5K', 'raceTimeHalf', 'raceTimeMarathon', 'userProfilePK']

  - cols only in temp: ['currentPredictedRaceTime', 'device_id', 'feedbackPhrase', 'lowerBoundProjectionRaceTime', 'midpointProjectionRaceTime', 'primaryTrainingDevice', 'race_time_10k', 'race_time_5k', 'race_time_half', 'race_time_marathon']...

  - date_range existing=('2022-07-12', '2026-06-29'), temp=('1970-01-01', '2026-06-29')

- readiness: rows existing=2131, temp=2131; cols existing=31, temp=30

  - cols only in existing: ['calendarDate', 'deviceId', 'timestampLocal', 'userProfilePK']

  - cols only in temp: ['device_id', 'timestamp_local', 'user_id']

  - date_range existing=('2023-06-14', '2026-06-29'), temp=('2023-06-14', '2026-06-29')

- maxmet: rows existing=1099, temp=1186; cols existing=16, temp=18

  - cols only in existing: ['calendarDate', 'deviceId', 'maxMet', 'userProfilePK', 'vo2MaxValue']

  - cols only in temp: ['activity_id', 'activity_uuid', 'device_id', 'max_met', 'timestamp', 'user_id', 'vo2max']

  - date_range existing=('2021-02-25', '2026-06-29'), temp=('2019-05-21', '2026-06-29')

- history: rows existing=4063, temp=4063; cols existing=16, temp=15

  - cols only in existing: ['calendarDate', 'deviceId', 'userProfilePK']

  - cols only in temp: ['device_id', 'user_id']

  - date_range existing=('2021-02-22', '2026-06-29'), temp=('2021-02-22', '2026-06-29')

- daily_master: rows existing=1167, temp=1167; cols existing=50, temp=47

  - cols only in existing: ['maxMet', 'run_count', 'vo2MaxValue']

  - date_range existing=('2018-06-11', '2026-06-29'), temp=('2018-06-11', '2026-06-29')


