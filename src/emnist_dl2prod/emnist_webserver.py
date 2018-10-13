"""
Flask Webserver module that sets up a simple Webserver
to handle Prediction Requests

Run with `emist_webservice` that is available as a command
when `emnist_dl2prod` was installed

Alternatively use `FLASK_APP=emnist_webserver.py flask run`
"""
__author__ = "Marcel Kurovski"
__copyright__ = "Marcel Kurovski"
__license__ = "mit"

import logging
import os
import pdb
from pkg_resources import resource_filename
import time

from flask import (Flask, request, url_for, render_template, abort,
                   send_from_directory)
import numpy as np
import onnx
from onnx_tf.backend import prepare
from skimage.io import imread

from emnist_dl2prod.models import Model
from emnist_dl2prod.utils import get_emnist_mapping, setup_logging


dnn_classifier_tf_module = 'emnist_dl2prod.resources.models.dnn_classifier_tf'
dnn_classifier_tf_resource = resource_filename(dnn_classifier_tf_module, '')
dnn_classifier_tf = Model(dnn_classifier_tf_resource)

dnn_classifier_onnx_module = 'emnist_dl2prod.resources.models.dnn_classifier_onnx'
dnn_classifier_onnx_resource = resource_filename(dnn_classifier_onnx_module,
                                                 'dnn_model_pt.onnx')
dnn_classifier_onnx = onnx.load(dnn_classifier_onnx_resource)
dnn_classifier_onnx = prepare(dnn_classifier_onnx)

_logger = logging.getLogger(__name__)
setup_logging(logging.INFO)

emnist_mapping = get_emnist_mapping()

app = Flask(__name__)
TEMP_MEDIA_FOLDER = os.path.join(os.getcwd(), 'tmp_flask_media')
os.mkdir(TEMP_MEDIA_FOLDER)
_logger.info("Set up temporary media folder for webserver: %s", TEMP_MEDIA_FOLDER)
app.config['UPLOAD_FOLDER'] = TEMP_MEDIA_FOLDER


@app.route('/emnist/img_upload', methods=['GET', 'POST'])
def upload_file():
    return render_template('img_upload.html')


@app.route('/emnist/result', methods=['POST'])
def show_emnist_result():
    """
    Handles HTTP request by classifying the image
    that is provided as part of the request.
    """
    emnist_result = {}
    timestamp = int(time.time()*1000)
    emnist_result['timestamp'] = timestamp

    # TODO: Check whether this works also without saving the image
    img_file = request.files['image']
    pdb.set_trace()
    img_filename = 'img_upload_' + str(timestamp) + '.png'
    img_filepath = os.path.join(app.config['UPLOAD_FOLDER'], img_filename)
    img_file.save(img_filepath)

    if '.png' not in img_file.filename:
        abort(415, "No .png-file provided")

    emnist_result['img_filename'] = url_for('get_file', filename=img_filename)

    img_raw = imread(img_file)
    img_prep = preprocess_img(img_raw)
    softmax_scores, class_prediction = classify_img(img_prep)

    emnist_result['softmax_scores'] = dict(zip(list(emnist_mapping.values()),
                                               list(np.round(softmax_scores, 4))))
    emnist_result['predicted_class'] = class_prediction

    return show_emnist_success(emnist_result)


@app.route('/emnist/img_upload/<path:filename>')
def get_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename,
                               as_attachment=True)


def show_emnist_success(emnist_result):
    """
    Handles a successful image detection
    and returns the render_template for Flask

    Args:
        emnist_result (dict): Request processing and result information

    Returns:
        (:obj:`flask.render_template`)
    """
    return render_template('result.html', **emnist_result)


def preprocess_img(img_raw):
    """
    Flattens and normalizes raw image array

    Args:
        img_raw (:obj:`np.array`): (width, height) image with single pixel
                                   values among 0 and 255

    Returns:
        img_prep (:obj:`np.array`): (1, width*height) flattened image with
                                    pixel values normalized to [0, 1]
    """
    img_prep = img_raw.reshape(1, -1).astype(np.float32)
    img_prep /= 255

    return img_prep


def classify_img(img_prep):
    """
    Performs image classification

    Returns:
        softmax_scores (:obj:`np.array`): (62,) array with softmax activations
            for all classes
        class_prediction (str): class with highest activation
    """
    softmax_scores = dnn_classifier.run(img_prep)[0]
    class_prediction_idx = np.argmax(softmax_scores)
    class_prediction = emnist_mapping[class_prediction_idx]

    return softmax_scores, class_prediction


def main():
    app.run(host="0.0.0.0", port=5000, debug=False)