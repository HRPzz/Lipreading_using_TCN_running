#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2020 Imperial College London (Pingchuan Ma)
# Apache 2.0  (http://www.apache.org/licenses/LICENSE-2.0)

""" Crop Mouth ROIs from videos for lipreading"""

# from msilib.schema import File
from ast import Pass
import os
import cv2  # OpenCV 라이브러리
import glob  # 리눅스식 경로 표기법을 사용하여 원하는 폴더/파일 리스트 얻음
import argparse  # 명령행 인자를 파싱해주는 모듈
import numpy as np
from collections import deque  # collections 모듈에 있는 데크 불러오기 # 데크: 스택과 큐를 합친 자료구조

from utils import *  # utils.py 모듈에 있는 모든 함수 불러오기
from transform import *  # transform.py 모듈에 있는 모든 함수(linear_interpolate(), warp_img(), apply_transform(), cut_patch(), convert_bgr2gray()) 불러오기

import dlib  # face landmark 찾는 라이브러리
import face_alignment  # face landmark 찾는 라이브러리
from PIL import Image
from torchvision.transforms.functional import to_tensor


# 인자값을 받아서 처리하는 함수
def load_args(default_config=None):
    # 인자값을 받아서 처리하는 함수
    parser = argparse.ArgumentParser(description='Lipreading Pre-processing')

    # 입력받을 인자값 등록
    # -- utils
    parser.add_argument('--video-direc', default=None, help='raw video directory')
    parser.add_argument('--video-format', default='.mp4', help='raw video format')
    parser.add_argument('--landmark-direc', default=None, help='landmark directory')
    parser.add_argument('--filename-path', default='./lrw500_detected_face.csv', help='list of detected video and its subject ID')
    parser.add_argument('--save-direc', default=None, help='the directory of saving mouth ROIs')
    # -- mean face utils
    parser.add_argument('--mean-face', default='./20words_mean_face.npy', help='mean face pathname')
    # -- mouthROIs utils
    parser.add_argument('--crop-width', default=96, type=int, help='the width of mouth ROIs')
    parser.add_argument('--crop-height', default=96, type=int, help='the height of mouth ROIs')
    parser.add_argument('--start-idx', default=48, type=int, help='the start of landmark index')
    parser.add_argument('--stop-idx', default=68, type=int, help='the end of landmark index')
    parser.add_argument('--window-margin', default=12, type=int, help='window margin for smoothed_landmarks')
    # -- convert to gray scale
    parser.add_argument('--convert-gray', default=True, action='store_true', help='convert2grayscale')
    # -- test set only
    parser.add_argument('--testset-only', default=False, action='store_true', help='process testing set only')

    # 입력받은 인자값을 args에 저장 (type: namespace)
    args = parser.parse_args()
    return args

args = load_args()  # args 파싱 및 로드

# -- mean face utils
STD_SIZE = (256, 256)
mean_face_landmarks = np.load(args.mean_face)  # 20words_mean_face.npy
stablePntsIDs = [33, 36, 39, 42, 45]


# 영상에서 랜드마크 받아서 입술 잘라내기
def crop_patch( video_pathname, landmarks):

    """Crop mouth patch
    :param str video_pathname: pathname for the video_dieo  # 영상 위치
    :param list landmarks: interpolated landmarks  # 보간된 랜드마크
    """

    frame_idx = 0  # 프레임 인덱스 번호 0 으로 초기화
    frame_gen = read_video(video_pathname)  # 비디오 불러오기
    
    # 무한 반복
    while True:
        try:
            frame = frame_gen.__next__() ## -- BGR  # 이미지 프레임 하나씩 불러오기
        except StopIteration:  # 더 이상 next 요소가 없으면 StopIterraion Exception 발생
            break  # while 빠져나가기
        if frame_idx == 0:  # 프레임 인덱스 번호가 0일 경우
            q_frame, q_landmarks = deque(), deque()  # 데크 생성
            sequence = []

        q_landmarks.append(landmarks[frame_idx])  # 프레임 인덱스 번호에 맞는 랜드마크 정보 추가
        q_frame.append(frame)  # 프레임 정보 추가
        if len(q_frame) == args.window_margin:
            print()
            print()
            # print(f'### q_landmarks: {q_landmarks}')
            print(f'### type: {type(q_landmarks)}')
            print(f'### len: {len(q_landmarks)}')
            smoothed_landmarks = np.mean(q_landmarks, axis=0)  # 각 그룹의 같은 원소끼리 평균
            # print(f'### smoothed_landmarks: {smoothed_landmarks}')
            print(f'### type: {type(smoothed_landmarks)}')
            print(f'### len: {len(smoothed_landmarks)}')
            print(f'### shape: {smoothed_landmarks.shape}')
            print()
            print()
            cur_landmarks = q_landmarks.popleft()  # 데크 제일 왼쪽 값 꺼내기
            cur_frame = q_frame.popleft()  # 데크 제일 왼쪽 값 꺼내기
            # -- affine transformation  # 아핀 변환
            trans_frame, trans = warp_img( smoothed_landmarks[stablePntsIDs, :],
                                           mean_face_landmarks[stablePntsIDs, :],
                                           cur_frame,
                                           STD_SIZE)
            trans_landmarks = trans(cur_landmarks)
            # -- crop mouth patch  # 입술 잘라내기
            sequence.append( cut_patch( trans_frame,
                                        trans_landmarks[args.start_idx:args.stop_idx],
                                        args.crop_height//2,
                                        args.crop_width//2,))
        if frame_idx == len(landmarks)-1:
            while q_frame:
                cur_frame = q_frame.popleft()  # 데크 제일 왼쪽 값 꺼내기
                # -- transform frame  # 프레임 변환
                trans_frame = apply_transform( trans, cur_frame, STD_SIZE)
                # -- transform landmarks  # 랜드마크 변환
                trans_landmarks = trans(q_landmarks.popleft())
                # -- crop mouth patch  # 입술 잘라내기
                sequence.append( cut_patch( trans_frame,
                                            trans_landmarks[args.start_idx:args.stop_idx],
                                            args.crop_height//2,
                                            args.crop_width//2,))
            return np.array(sequence)  # 입술 numpy 반환
        frame_idx += 1  # 프레임 인덱스 번호 증가
    return None


# 랜드마크 보간
def landmarks_interpolate(landmarks):
    
    """Interpolate landmarks
    param list landmarks: landmarks detected in raw videos  # 원본 영상 데이터에서 검출한 랜드마크
    """

    valid_frames_idx = [idx for idx, _ in enumerate(landmarks) if _ is not None]  # 랜드마크 번호 list 생성

    # 랜드마크 번호 list 가 비어있다면
    if not valid_frames_idx:
        return None

    # 1부터 (랜드마크 번호 list 개수-1)만큼 for 문 반복
    for idx in range(1, len(valid_frames_idx)):
        if valid_frames_idx[idx] - valid_frames_idx[idx-1] == 1:  # 현재 랜드마크 번호 - 이전 랜드마크 번호 == 1 일 경우
            continue  # 코드 실행 건너뛰기
        else:  # 아니라면
            landmarks = linear_interpolate(landmarks, valid_frames_idx[idx-1], valid_frames_idx[idx])  # 랜드마크 업데이트(보간)

    valid_frames_idx = [idx for idx, _ in enumerate(landmarks) if _ is not None]  # 랜드마크 번호 list 생성
    # -- Corner case: keep frames at the beginning or at the end failed to be detected.  # 시작 또는 끝 프레임을 보관하지 못함
    if valid_frames_idx:
        landmarks[:valid_frames_idx[0]] = [landmarks[valid_frames_idx[0]]] * valid_frames_idx[0]  # 랜드마크 첫번째 프레임 정보 저장
        landmarks[valid_frames_idx[-1]:] = [landmarks[valid_frames_idx[-1]]] * (len(landmarks) - valid_frames_idx[-1])  # 랜드마크 마지막 프레임 정보 저장

    valid_frames_idx = [idx for idx, _ in enumerate(landmarks) if _ is not None]  # 랜드마크 번호 list 생성
    # 랜드마크 번호 list 개수 == 보간한 랜드마크 개수 확인, 아니면 AssertionError 메시지를 띄움
    assert len(valid_frames_idx) == len(landmarks), "not every frame has landmark"  # 원하는 조건의 변수값을 보증하기 위해 사용

    return landmarks  # 랜드마크 반환


os.environ['CUDA_LAUNCH_BLOCKING'] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = "0"


lines = open(args.filename_path).read().splitlines()  # 문자열을 '\n' 기준으로 쪼갠 후 list 생성
lines = list(filter(lambda x: 'test' == x.split('/')[-2], lines)) if args.testset_only else lines  # args.testset_only 값이 있다면 test 폴더 속 파일명만 불러와서 list 생성, 아니라면 원래 lines 그대로 값 유지

# lines 개수만큼 반복문 실행
for filename_idx, line in enumerate(lines):

    # 파일명, 사람id
    filename, person_id = line.split(',')
    print('idx: {} \tProcessing.\t{}'.format(filename_idx, filename))  # 파일 인덱스번호, 파일명 출력

    video_pathname = os.path.join(args.video_direc, filename+args.video_format)  # 영상디렉토리 + 파일명.비디오포맷/
    landmarks_pathname = os.path.join(args.landmark_direc, filename+'.npz')  # 저장디렉토리 + 랜드마크 파일명.npz
    dst_pathname = os.path.join( args.save_direc, filename+'.npz')  # 저장디렉토리 + 결과영상 파일명.npz

    # 파일이 있는지 확인, 없으면 AssertionError 메시지를 띄움
    assert os.path.isfile(video_pathname), "File does not exist. Path input: {}".format(video_pathname)  # 원하는 조건의 변수값을 보증하기 위해 사용
    
    # video 에 대한 face landmark npz 파일이 없고 영상 확장자 avi 인 경우 dlib 으로 직접 npz 파일 생성
    if not os.path.exists(landmarks_pathname) and video_pathname.split('.')[-1] == 'avi':
        
        # dlib 사용해서 face landmark 찾기
        def get_face_landmark(img):
            detector_hog = dlib.get_frontal_face_detector()
            dlib_rects = detector_hog(img, 1)
            model_path = os.path.dirname(os.path.abspath(__file__)) + '/shape_predictor_68_face_landmarks.dat'
            landmark_predictor = dlib.shape_predictor(model_path)
            
            list_landmarks = []
            for dlib_rect in dlib_rects:
                points = landmark_predictor(img, dlib_rect)
                list_points = list(map(lambda p: (p.x, p.y), points.parts()))
                list_landmarks.append(list_points)
            
            for dlib_rect, landmark in zip(dlib_rects, list_landmarks):
                
                # CROP_START_X = landmark[5][0]
                # CROP_START_Y = landmark[29][1]
                # CROP_END_X = landmark[11][0]
                # CROP_END_Y = landmark[8][1]
                
                # crop_img = img[CROP_START_Y:CROP_END_Y,CROP_START_X:CROP_END_X]  # 입술 crop

                CROP_START_X = landmark[0][0]
                CROP_START_Y = landmark[29][1]
                CROP_END_X = landmark[19][0]
                CROP_END_Y = landmark[8][1]
                # face_img = img[CROP_START_Y:CROP_END_Y,CROP_START_X:CROP_END_X]  # 얼굴 crop
                # face_img = img[CROP_START_Y:CROP_END_Y,CROP_START_X:CROP_END_X]  # 얼굴 crop
                face_img = np.array(landmark)  # 얼굴 crop
                print(face_img.shape)

                # eye_img = img[CROP_START_Y:CROP_END_Y,CROP_START_X:CROP_END_X]  # 눈 crop
                eye_img = np.array(landmark[36:48])  # 눈 crop
                print(eye_img.shape)

                # face_img = to_tensor(face_img)
                # eye_img = to_tensor(eye_img)

                return face_img, eye_img


                
                # SAVE_IMG_SIZE = (96,96)
                # WORD = video_pathname.split('/')[-1].split('_')[0]
                # WORD_NUM = video_pathname.split('/')[-1][:-4]
                # SAVE_IMG_PATH = os.path.dirname(os.path.abspath(__file__)) + f'/{WORD}/{WORD_NUM}/{WORD_NUM}_{frame_idx}.png'
                # # if not os.path.exists(os.path.dirname(SAVE_IMG_PATH)):                            
                # #     os.makedirs(os.path.dirname(SAVE_IMG_PATH))  # 디렉토리 생성
                
                # save_img = Image.fromarray(crop_img)  # numpy to image
                # save_img = save_img.resize(SAVE_IMG_SIZE)  # 입술 이미지 크기 (96,96)
                # # save_img.save(SAVE_IMG_PATH)  # 입술 이미지 저장
                
                # crop_img = np.asarray(save_img)  # image to numpy
                # crop_img = to_tensor(crop_img)
                
                # return crop_img           
        
        
        target_frames = 29  # 원하는 프레임 개수
        # video = videoToArray(video_pathname, is_gray=args.convert_gray)  # 영상 정보 앞에 영상 프레임 개수를 추가한 numpy
        video = videoToArray(video_pathname, is_gray=True)  # 영상 정보 앞에 영상 프레임 개수를 추가한 numpy
        output_video = frameAdjust(video, target_frames)  # frame sampling (프레임 개수 맞추기)

        from torchvision import transforms as transforms
        from torchvision.transforms import ToTensor, ToPILImage
        from PIL import Image


        img_transform = transforms.Compose(
            [
                transforms.Grayscale(num_output_channels=1),  # gray
                transforms.ToTensor(),  # image to tensor
                transforms.Normalize((0.5,),(0.5,)),  # gray image 를 color image 로 load 하기 위함 # 참고: https://github.com/pytorch/vision/issues/288
                # transforms.Lambda(lambda x: x.to('cuda'))
            ]
        )
        
        def get_yield(output_video, img_transform):
            for frame in output_video:
                # frame = Image.fromarray(np.uint8(frame))  # numpy to image
                # frame_torch = img_transform(frame)
                # frame = frame_torch.numpy()
                yield frame
        
        multi_sub_landmarks = []
        person_landmarks = []
        frame_landmarks = []
        for frame_idx, frame in enumerate(get_yield(output_video, img_transform)):
            print(f'\n{frame_idx}번째 프레임 랜드마크 찾기')
            
            # print()
            # print(f'#### type(frame): {type(frame)}')
            # print(f'#### len(frame): {len(frame)}')
            # print(f'#### frame.shape: {frame.shape}')
            # print(f'#### frame_idx: {frame_idx}, person_id: {person_id}')
            # print()
            facial_landmaarks, eye_landmarks = get_face_landmark(frame)  # dlib 사용해서 face landmark 찾기            
            person_landmarks = {
                'id': 0,
                'most_recent_fitting_scores': np.array([2.0,2.0,2.0]),
                'facial_landmarks': facial_landmaarks,
                'roll': 7,
                'yaw': 3.5,
                'eye_landmarks': eye_landmarks,
                'fitting_scores_updated': True,
                'pitch': -0.05
            }
            frame_landmarks.append(person_landmarks)  # person_id
            multi_sub_landmarks.append(np.array(frame_landmarks.copy(), dtype=object))

            print()
            # print(f'111 landmarks: {landmarks}')
            # print(f'111 keys: {landmarks.keys()}')
            # print(f'111 values: {landmarks.values()}')
            # print(f'111 type: {type(landmarks)}')
            # print(f'111 len: {len(landmarks)}')
            # print(f'111 shape: {landmarks.shape}')
            print()
            # print(f'222 person_landmarks: {person_landmarks}')
            # print(f'222 type: {type(person_landmarks)}')
            # print(f'222 len: {len(person_landmarks)}')
            # print(f'222 shape: {person_landmarks.shape}')
            print()
            # print(f'333 multi_sub_landmarks: {multi_sub_landmarks}')
            print(f'333 type: {type(multi_sub_landmarks)}')
            print(f'333 len: {len(multi_sub_landmarks)}')
            # print(f'333 shape: {multi_sub_landmarks.shape}')
            print()
            
            print()
            print('저장')
            print()

        
        # multi_sub_landmarks.append(person_landmarks)  # frame_idx
        # print()
        # print(f'444 person_landmarks: {person_landmarks}')
        # print()
        # multi_sub_landmarks = {frame_idx: person_landmarks}  # frame_idx
        multi_sub_landmarks = np.array(multi_sub_landmarks)  # list to numpy
        
        # print()
        # print()
        # print(f'\n######### len(multi_sub_landmarks): {len(multi_sub_landmarks)}')  # list to numpy
        # print(f'\n######### frame_idx - {frame_idx}: {multi_sub_landmarks[frame_idx]}')  # list to numpy
        # print(f'\n######### person_id - {person_id}: {multi_sub_landmarks[frame_idx][int(person_id)]}')  # list to numpy
        # print(f'\n######### facial_landmarks: {multi_sub_landmarks[frame_idx][int(person_id)]["facial_landmarks"]}')  # list to numpy
        # print()
        # print()
        
        # save2npz(dst_pathname, data=multi_sub_landmarks)  # face landmark npz 저장
        save2npz(landmarks_pathname, data=multi_sub_landmarks)  # face landmark npz 저장
        
        print()
        print('npz 저장')
        print()
    
    # video 에 대한 face landmark npz 파일이 있는 경우
    else:
        
        # 파일이 있는지 확인, 없으면 AssertionError 메시지를 띄움
        assert os.path.isfile(landmarks_pathname), "File does not exist. Path input: {}".format(landmarks_pathname)  # 원하는 조건의 변수값을 보증하기 위해 사용

        # 파일이 존재할 경우
        if os.path.exists(dst_pathname):
            continue  # 코드 실행 건너뛰기

        multi_sub_landmarks = np.load( landmarks_pathname, allow_pickle=True)['data']  # numpy 파일 열기
        landmarks = [None] * len( multi_sub_landmarks)  # 랜드마크 변수 초기화
        for frame_idx in range(len(landmarks)):
            try:
                landmarks[frame_idx] = multi_sub_landmarks[frame_idx][int(person_id)]['facial_landmarks']  # 프레임 인덱스 번호에서 사람id의 얼굴 랜드마크 정보 가져오기
                print()
                print()
                # print(f'landmarks[frame_idx]: {landmarks[frame_idx]}')
                print(f'len: {len(landmarks[frame_idx])}')
                print()
                # print(f'111 multi_sub_landmarks: {multi_sub_landmarks}')
                print(f'111 type: {type(multi_sub_landmarks)}')
                print(f'111 len: {len(multi_sub_landmarks)}')
                print(f'111 shape: {multi_sub_landmarks.shape}')
                print()
                # print(f'222 frame_idx: {multi_sub_landmarks[frame_idx]}')
                print(f'222 type: {type(multi_sub_landmarks[frame_idx])}')
                print(f'222 len: {len(multi_sub_landmarks[frame_idx])}')
                print(f'222 shape: {multi_sub_landmarks[frame_idx].shape}')
                print()
                # print(f'333 person_id: {multi_sub_landmarks[frame_idx][int(person_id)]}')
                print(f'333 type: {type(multi_sub_landmarks[frame_idx][int(person_id)])}')
                print(f'333 len: {len(multi_sub_landmarks[frame_idx][int(person_id)])}')
                # print(f'333 keys: {multi_sub_landmarks[frame_idx][int(person_id)].keys()}')
                # print(f'333 values: {multi_sub_landmarks[frame_idx][int(person_id)].values()}')
                print()
                print()
                # print(q)
            except IndexError:  # 해당 인덱스 번호에 깂이 없으면 IndexError 발생
                continue  # 코드 실행 건너뛰기

        # -- pre-process landmarks: interpolate frames not being detected.
        preprocessed_landmarks = landmarks_interpolate(landmarks)  # 랜드마크 보간
        # 변수가 비어있지 않다면
        if not preprocessed_landmarks:
            continue  # 코드 실행 건너뛰기

        # -- crop
        sequence = crop_patch(video_pathname, preprocessed_landmarks)  # 영상에서 랜드마크 받아서 입술 잘라내기
        # sequence가 비어있는지 확인, 비어있으면 AssertionError 메시지를 띄움
        assert sequence is not None, "cannot crop from {}.".format(filename)  # 원하는 조건의 변수값을 보증하기 위해 사용

        # -- save
        data = convert_bgr2gray(sequence) if args.convert_gray else sequence[...,::-1]  # gray 변환
        save2npz(dst_pathname, data=data)  # 데이터를 npz 형식으로 저장

print('Done.')