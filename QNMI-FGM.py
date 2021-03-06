"""Implementation of sample attack."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import math
import numpy as np
from scipy.misc import imread,imresize
from scipy.misc import imsave

import tensorflow as tf
from nets import inception_v3, inception_v4, inception_resnet_v2, resnet_v2

slim = tf.contrib.slim
os.environ["CUDA_VISIBLE_DEVICES"] = "0,1" #GPU selection"0,1" means choose 0# and 1# GPU

tf.flags.DEFINE_string(
    'master', '', 'The address of the TensorFlow master to use.')

tf.flags.DEFINE_string(
    'checkpoint_path_inception_v3', '', 'Path to checkpoint for inception network.')

tf.flags.DEFINE_string(
    'checkpoint_path_adv_inception_v3', '', 'Path to checkpoint for inception network.')

tf.flags.DEFINE_string(
    'checkpoint_path_ens3_adv_inception_v3', '', 'Path to checkpoint for inception network.')

tf.flags.DEFINE_string(
    'checkpoint_path_ens4_adv_inception_v3', '', 'Path to checkpoint for inception network.')

tf.flags.DEFINE_string(
    'checkpoint_path_inception_v4', '', 'Path to checkpoint for inception network.')

tf.flags.DEFINE_string(
    'checkpoint_path_inception_resnet_v2', '', 'Path to checkpoint for inception network.')

tf.flags.DEFINE_string(
    'checkpoint_path_ens_adv_inception_resnet_v2', '', 'Path to checkpoint for inception network.')

tf.flags.DEFINE_string(
    'checkpoint_path_resnet', '', 'Path to checkpoint for inception network.')

tf.flags.DEFINE_string(
    'input_dir', '', 'Input directory with images.')

tf.flags.DEFINE_string(
    'output_dir', '', 'Output directory with images.')

tf.flags.DEFINE_float(
    'max_epsilon', 16.0, 'Maximum size of adversarial perturbation.')

tf.flags.DEFINE_integer(
    'num_iter', 10, 'Number of iterations.')

tf.flags.DEFINE_integer(
    'image_width', 299, 'Width of each input images.')

tf.flags.DEFINE_integer(
    'image_height', 299, 'Height of each input images.')

tf.flags.DEFINE_integer(
    'batch_size', 10, 'How many images process at one time.')

tf.flags.DEFINE_float(
    'momentum', 1.0, 'Momentum.')

FLAGS = tf.flags.FLAGS


def load_images(input_dir, batch_shape):
  """Read png images from input directory in batches.

  Args:
    input_dir: input directory
    batch_shape: shape of minibatch array, i.e. [batch_size, height, width, 3]

  Yields:
    filenames: list file names without path of each image
      Lenght of this list could be less than batch_size, in this case only
      first few images of the result are elements of the minibatch.
    images: array with all images from this batch
  """
  images = np.zeros(batch_shape)
  filenames = []
  idx = 0
  batch_size = batch_shape[0]
  for filepath in tf.gfile.Glob(os.path.join(input_dir, '*.JPEG')):
    with tf.gfile.Open(filepath, 'rb') as f:
        #image = imread(f, mode='RGB').astype(np.float)
        image = imread(f, mode='RGB').astype(np.float) / 255.0
        #image = imresize(image,(FLAGS.image_width, FLAGS.image_height)) / 255.0
    # Images for inception classifier are normalized to be in [-1, 1] interval.
    images[idx, :, :, :] = image * 2.0 - 1.0
    filenames.append(os.path.basename(filepath))
    idx += 1
    if idx == batch_size:
      yield filenames, images
      filenames = []
      images = np.zeros(batch_shape)
      idx = 0
  if idx > 0:
    yield filenames, images


def save_images(images, filenames, output_dir):
  """Saves images to the output directory.

  Args:
    images: array with minibatch of images
    filenames: list of filenames without path
      If number of file names in this list less than number of images in
      the minibatch then only first len(filenames) images will be saved.
    output_dir: directory where to save images
  """
  for i, filename in enumerate(filenames):
    # Images for inception classifier are normalized to be in [-1, 1] interval,
    # so rescale them back to [0, 1].
    with tf.gfile.Open(os.path.join(output_dir, filename), 'w') as f:
      imsave(f, (images[i, :, :, :] + 1.0) * 0.5, format='JPEG')


def graph(x, y, i, x_max, x_min, grad1, grad2, t):
  eps = 2 * tf.sqrt(299.0 * 299.0 * 3) * FLAGS.max_epsilon / 255.0
  num_iter = FLAGS.num_iter
  alpha = eps / num_iter
  momentum = FLAGS.momentum
  num_classes = 1001

  with slim.arg_scope(inception_v3.inception_v3_arg_scope()):
    logits_v3, end_points_v3 = inception_v3.inception_v3(
        x, num_classes=num_classes, is_training=False)

  # with slim.arg_scope(inception_v3.inception_v3_arg_scope()):
  #   logits_adv_v3, end_points_adv_v3 = inception_v3.inception_v3(
  #       x, num_classes=num_classes, is_training=False, scope='AdvInceptionV3')

  with slim.arg_scope(inception_v3.inception_v3_arg_scope()):
    logits_ens3_adv_v3, end_points_ens3_adv_v3 = inception_v3.inception_v3(
        x, num_classes=num_classes, is_training=False, scope='Ens3AdvInceptionV3')

  with slim.arg_scope(inception_v3.inception_v3_arg_scope()):
    logits_ens4_adv_v3, end_points_ens4_adv_v3 = inception_v3.inception_v3(
        x, num_classes=num_classes, is_training=False, scope='Ens4AdvInceptionV3')

  # with slim.arg_scope(inception_v4.inception_v4_arg_scope()):
  #   logits_v4, end_points_v4 = inception_v4.inception_v4(
  #       x, num_classes=num_classes, is_training=False)

  with slim.arg_scope(inception_resnet_v2.inception_resnet_v2_arg_scope()):
    logits_res_v2, end_points_res_v2 = inception_resnet_v2.inception_resnet_v2(
        x, num_classes=num_classes, is_training=False)

  with slim.arg_scope(inception_resnet_v2.inception_resnet_v2_arg_scope()):
    logits_ensadv_res_v2, end_points_ensadv_res_v2 = inception_resnet_v2.inception_resnet_v2(
        x, num_classes=num_classes, is_training=False, scope='EnsAdvInceptionResnetV2')

  with slim.arg_scope(resnet_v2.resnet_arg_scope()):
    logits_resnet, end_points_resnet = resnet_v2.resnet_v2_101(
        x, num_classes=num_classes, is_training=False)
            
  # pred = tf.argmax(end_points_v3['Predictions'] + end_points_adv_v3['Predictions'] + end_points_ens3_adv_v3['Predictions'] + \
  #                 end_points_ens4_adv_v3['Predictions'] + end_points_v4['Predictions'] + \
  #                 end_points_res_v2['Predictions'] + end_points_ensadv_res_v2['Predictions'] + end_points_resnet['predictions'], 1)

  pred = tf.argmax(end_points_v3['Predictions'] + end_points_ens3_adv_v3['Predictions'] + \
                  end_points_ens4_adv_v3['Predictions']+ \
                  end_points_res_v2['Predictions'] + end_points_ensadv_res_v2['Predictions'] + end_points_resnet['predictions'], 1)

  first_round = tf.cast(tf.equal(i, 0), tf.int64)
  y = first_round * pred + (1 - first_round) * y
  one_hot = tf.one_hot(y, num_classes)

  # logits = (logits_v3 + 0.25 * logits_adv_v3 + logits_ens3_adv_v3 + \
  #          logits_ens4_adv_v3 + logits_v4 + \
  #          logits_res_v2 + logits_ensadv_res_v2 + logits_resnet) / 7.25
  # auxlogits = (end_points_v3['AuxLogits'] + 0.25 * end_points_adv_v3['AuxLogits'] + end_points_ens3_adv_v3['AuxLogits'] + \
  #             end_points_ens4_adv_v3['AuxLogits'] + end_points_v4['AuxLogits'] + \
  #             end_points_res_v2['AuxLogits'] + end_points_ensadv_res_v2['AuxLogits']) / 6.25

  logits = (logits_v3 + logits_ens3_adv_v3 + \
           logits_ens4_adv_v3 + \
           logits_res_v2 + logits_ensadv_res_v2 + logits_resnet) / 6.0
  auxlogits = (end_points_v3['AuxLogits'] + end_points_ens3_adv_v3['AuxLogits'] + \
              end_points_ens4_adv_v3['AuxLogits'] + \
              end_points_res_v2['AuxLogits'] + end_points_ensadv_res_v2['AuxLogits']) / 5.0

  cross_entropy = tf.losses.softmax_cross_entropy(one_hot,
                                                  logits,
                                                  label_smoothing=0.0,
                                                  weights=1.0)
  cross_entropy += tf.losses.softmax_cross_entropy(one_hot,
                                                   auxlogits,
                                                   label_smoothing=0.0,
                                                   weights=0.4)

  noise = tf.gradients(cross_entropy, x)[0]
  b = tf.random_normal(shape=grad1.shape, mean=0, stddev=1.0)
  prob = 0.4 / (100 * ((i + 1) / FLAGS.num_iter))
  b1 = tf.nn.dropout(b, keep_prob=prob)
  b2 = tf.sign(b1)
  b3 = 0.5 * tf.ones(shape=grad1.shape) + b2
  b4 = tf.sign(b3)
  noise = (noise / tf.reduce_mean(tf.abs(noise), [1, 2, 3], keepdims=True))
  grad = momentum * grad2 + noise + (1.0 - (1.0 / FLAGS.num_iter) * i) * momentum * (grad2 - grad1)
  grad1 = grad2
  grad2 = grad
  grad3 = grad * b4
  noise_norm = tf.norm(grad3, axis=(1, 2), ord='fro', keepdims=True)
  x = x + alpha * (grad3 / noise_norm)
  x = tf.clip_by_value(x, x_min, x_max)
  i = tf.add(i, 1)
  return x, y, i, x_max, x_min, grad1, grad2, t

def stop(x, y, i, x_max, x_min, grad1, grad2, t):
  num_iter = FLAGS.num_iter
  return tf.less(i, num_iter)


def main(_):
  # Images for inception classifier are normalized to be in [-1, 1] interval,
  # eps is a difference between pixels so it should be in [0, 2] interval.
  # Renormalizing epsilon from [0, 255] to [0, 2].
  eps = 2 * FLAGS.max_epsilon / 255.0

  batch_shape = [FLAGS.batch_size, FLAGS.image_height, FLAGS.image_width, 3]

  tf.logging.set_verbosity(tf.logging.INFO)

  with tf.Graph().as_default():
    # Prepare graph
    x_input = tf.placeholder(tf.float32, shape=batch_shape)
    x_max = tf.clip_by_value(x_input + eps, -1.0, 1.0)
    x_min = tf.clip_by_value(x_input - eps, -1.0, 1.0)

    y = tf.constant(np.zeros([FLAGS.batch_size]), tf.int64)
    i = tf.cast(tf.constant(0),tf.float32)
    grad1 = tf.zeros(shape=batch_shape)
    grad2 = tf.zeros(shape=batch_shape)
    t = tf.ones(shape=[1], dtype=tf.float32)
    x_adv, _, _, _, _, _, _, _ = tf.while_loop(stop, graph, [x_input, y, i, x_max, x_min, grad1, grad2, t])



    # Run computation
    s1 = tf.train.Saver(slim.get_model_variables(scope='InceptionV3'))
    #s2 = tf.train.Saver(slim.get_model_variables(scope='AdvInceptionV3'))
    s3 = tf.train.Saver(slim.get_model_variables(scope='Ens3AdvInceptionV3'))
    s4 = tf.train.Saver(slim.get_model_variables(scope='Ens4AdvInceptionV3'))
    # s5 = tf.train.Saver(slim.get_model_variables(scope='InceptionV4'))
    s6 = tf.train.Saver(slim.get_model_variables(scope='InceptionResnetV2'))
    s7 = tf.train.Saver(slim.get_model_variables(scope='EnsAdvInceptionResnetV2'))
    s8 = tf.train.Saver(slim.get_model_variables(scope='resnet_v2'))
    
    with tf.Session() as sess:
      s1.restore(sess, FLAGS.checkpoint_path_inception_v3)
      #s2.restore(sess, FLAGS.checkpoint_path_adv_inception_v3)
      s3.restore(sess, FLAGS.checkpoint_path_ens3_adv_inception_v3)
      s4.restore(sess, FLAGS.checkpoint_path_ens4_adv_inception_v3)
      # s5.restore(sess, FLAGS.checkpoint_path_inception_v4)
      s6.restore(sess, FLAGS.checkpoint_path_inception_resnet_v2)
      s7.restore(sess, FLAGS.checkpoint_path_ens_adv_inception_resnet_v2)
      s8.restore(sess, FLAGS.checkpoint_path_resnet)

      for filenames, images in load_images(FLAGS.input_dir, batch_shape):
        adv_images = sess.run(x_adv, feed_dict={x_input: images})
        save_images(adv_images, filenames, FLAGS.output_dir)

if __name__ == '__main__':
  tf.app.run()
