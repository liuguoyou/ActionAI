import sys
import cv2
import csv
import time
import numpy as np

import poses
import utils
import person
import model as mdl
import config as cfg
import control as ps3

timestamp = int(time.time() * 1000)

secondary_model = mdl.lstm_model()
secondary_model.compile(loss='categorical_crossentropy', 
                        optimizer=mdl.RMSprop(lr=cfg.learning_rate), 
                        metrics=['accuracy'])

if cfg.log:
    dataFile = open('data/logs/{}.csv'.format(timestamp), 'w')
    newFileWriter = csv.writer(dataFile)

if cfg.video:
    # Define the codec and create VideoWriter object
    name = 'data/videos/{}.mp4'.format(timestamp)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(name, fourcc, cfg.fps, (cfg.w, cfg.h))

trackers = []
cap = utils.source_capture(sys.argv[1])
img = utils.img_obj()

while True:

    ret, frame = cap.read()
    bboxes = []
    if ret:

        image, pose_list = poses.inference(frame)
        print(pose_list)
        for body in pose_list:
            bbox = utils.get_bbox(list(body.values()))
            bboxes.append((bbox, body))

        track_boxes = [tracker.bbox for tracker in trackers]
        matched, unmatched_trackers, unmatched_detections = utils.tracker_match(track_boxes, [b[0] for b in bboxes])

        for idx, jdx in matched:
            trackers[idx].set_bbox(bboxes[jdx][0])
            trackers[idx].set_pose(bboxes[jdx][1])
            trackers[idx].set_cubit(bboxes[jdx][1])

        for idx in unmatched_detections:
            try:
                trackers[idx].count += 1
                if trackers[idx].count > trackers[idx].expiration:
                    trackers.pop(idx)
            except:
                pass

        for idx in unmatched_trackers:
            p = person.PersonTracker()
            p.set_bbox(bboxes[idx][0])
            p.set_pose(bboxes[idx][1])
            p.set_cubit(bboxes[idx][1])
            trackers.append(p)

        print([(tracker.id, np.vstack(tracker.q)) for tracker in trackers])

        for tracker in trackers:
            activity = [cfg.activity_dict[x] for x in ps3.getButton()]
            print(activity)
            print('-------------------------')
            if len(tracker.q) >= cfg.window:
                sample = np.array(list(tracker.q)[:cfg.window])
                sample = sample.reshape(1, cfg.pose_vec_dim, cfg.window)
                if activity:
                    #activity_y = mdl.to_categorical(list(map(cfg.idx_dict.get, tracker.activity)), len(cfg.activity_dict))
                    activity_y = np.expand_dims(mdl.to_categorical(cfg.idx_dict[activity[0]], len(cfg.activity_dict)), axis=0)
                    secondary_model.fit(sample, activity_y, batch_size=1, epochs=1, verbose=1)
                    tracker.activity = activity
                else:
                    pred_activity = cfg.activity_idx[np.argmax(secondary_model.predict(sample)[0])]
                    tracker.activity = pred_activity

                print(tracker.activity)

            if cfg.log:
                newFileWriter.writerow([tracker.activity] + list(np.hstack(list(tracker.q)[:cfg.window])))
                    

        if cfg.video:
            for tracker in trackers:
                if len(tracker.q) >= cfg.window:
                    image = img.annotate(tracker, image)
            out.write(image)

        if cfg.display:
            cv2.imshow(sys.argv[1], image)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    else:
        break

cap.release()

try:
    dataFile.close()
except:
    pass

try:
    out.release()
except:
    pass
