#!/usr/bin/python3

import os;
import numpy as np;
import tensorflow as tf;
import tensorflow_datasets as tfds;
from models import CycleGAN;
from create_dataset import parse_function_generator;
from download_dataset import parse_function_generator;

batch_size = 1;
dataset_size = 1334;
img_shape = (255,255,3);

def main():

  # models
  cycleGAN = CycleGAN();
  optimizerGA = tf.keras.optimizers.Adam(
    tf.keras.optimizers.schedules.PiecewiseConstantDecay(
      boundaries = [dataset_size * 100 + i * dataset_size * 100 / 4 for i in range(5)],
      values = list(reversed([i * 2e-4 / 5 for i in range(6)]))),
    beta_1 = 0.5);
  optimizerGB = tf.keras.optimizers.Adam(
    tf.keras.optimizers.schedules.PiecewiseConstantDecay(
      boundaries = [dataset_size * 100 + i * dataset_size * 100 / 4 for i in range(5)],
      values = list(reversed([i * 2e-4 / 5 for i in range(6)]))),
    beta_1 = 0.5);
  optimizerDA = tf.keras.optimizers.Adam(
    tf.keras.optimizers.schedules.PiecewiseConstantDecay(
      boundaries = [dataset_size * 100 + i * dataset_size * 100 / 4 for i in range(5)],
      values = list(reversed([i * 2e-4 / 5 for i in range(6)]))),
    beta_1 = 0.5);
  optimizerDB = tf.keras.optimizers.Adam(
    tf.keras.optimizers.schedules.PiecewiseConstantDecay(
      boundaries = [dataset_size * 100 + i * dataset_size * 100 / 4 for i in range(5)],
      values = list(reversed([i * 2e-4 / 5 for i in range(6)]))),
    beta_1 = 0.5);
  
  # load dataset
  '''
  A = tf.data.TFRecordDataset(os.path.join('dataset', 'A.tfrecord')).map(parse_function_generator(img_shape)).shuffle(batch_size).batch(batch_size).__iter__();
  B = tf.data.TFRecordDataset(os.path.join('dataset', 'B.tfrecord')).map(parse_function_generator(img_shape)).shuffle(batch_size).batch(batch_size).__iter__();
  '''
  A = iter(tfds.load(name = 'cycle_gan/horse2zebra', split = "trainA", download = False).repeat(-1).map(parse_function_generator()).shuffle(batch_size).batch(batch_size).prefetch(tf.data.experimental.AUTOTUNE));
  B = iter(tfds.load(name = 'cycle_gan/horse2zebra', split = "trainB", download = False).repeat(-1).map(parse_function_generator()).shuffle(batch_size).batch(batch_size).prefetch(tf.data.experimental.AUTOTUNE));
  testA = iter(tfds.load(name = 'cycle_gan/horse2zebra', split = 'testA', download = False).repeat(-1).map(parse_function_generator(isTrain = False)).batch(1));
  testB = iter(tfds.load(name = 'cycle_gan/horse2zebra', split = 'testB', download = False).repeat(-1).map(parse_function_generator(isTrain = False)).batch(1));
  # restore from existing checkpoint
  checkpoint = tf.train.Checkpoint(GA = cycleGAN.GA, GB = cycleGAN.GB, DA = cycleGAN.DA, DB = cycleGAN.DB, 
                                   optimizerGA = optimizerGA, optimizerGB = optimizerGB, optimizerDA = optimizerDA, optimizerDB = optimizerDB);
  checkpoint.restore(tf.train.latest_checkpoint('checkpoints'));
  # create log
  log = tf.summary.create_file_writer('checkpoints');
  # train model
  avg_ga_loss = tf.keras.metrics.Mean(name = 'GA loss', dtype = tf.float32);
  avg_gb_loss = tf.keras.metrics.Mean(name = 'GB loss', dtype = tf.float32);
  avg_da_loss = tf.keras.metrics.Mean(name = 'DA loss', dtype = tf.float32);
  avg_db_loss = tf.keras.metrics.Mean(name = 'DB loss', dtype = tf.float32);
  while True:
    imageA, _ = next(A);
    imageB, _ = next(B);
    with tf.GradientTape(persistent = True) as tape:
      outputs = cycleGAN((imageA, imageB));
      GA_loss = cycleGAN.GA_loss(outputs);
      GB_loss = cycleGAN.GB_loss(outputs);
      DA_loss = cycleGAN.DA_loss(outputs);
      DB_loss = cycleGAN.DB_loss(outputs);
    # calculate discriminator gradients
    da_grads = tape.gradient(DA_loss, cycleGAN.DA.trainable_variables); avg_da_loss.update_state(DA_loss);
    db_grads = tape.gradient(DB_loss, cycleGAN.DB.trainable_variables); avg_db_loss.update_state(DB_loss);
    # calculate generator gradients
    ga_grads = tape.gradient(GA_loss, cycleGAN.GA.trainable_variables); avg_ga_loss.update_state(GA_loss);
    gb_grads = tape.gradient(GB_loss, cycleGAN.GB.trainable_variables); avg_gb_loss.update_state(GB_loss);
    # update discriminator weights
    optimizerDA.apply_gradients(zip(da_grads, cycleGAN.DA.trainable_variables));
    optimizerDB.apply_gradients(zip(db_grads, cycleGAN.DB.trainable_variables));
    # update generator weights
    optimizerGA.apply_gradients(zip(ga_grads, cycleGAN.GA.trainable_variables));
    optimizerGB.apply_gradients(zip(gb_grads, cycleGAN.GB.trainable_variables));
    if tf.equal(optimizerGA.iterations % 500, 0):
      imageA, _ = next(testA);
      imageB, _ = next(testB);
      outputs = cycleGAN((imageA, imageB));
      real_A = tf.cast(tf.clip_by_value((imageA + 1) * 127.5, clip_value_min = 0., clip_value_max = 255.), dtype = tf.uint8);
      real_B = tf.cast(tf.clip_by_value((imageB + 1) * 127.5, clip_value_min = 0., clip_value_max = 255.), dtype = tf.uint8);
      fake_B = tf.cast(tf.clip_by_value((outputs[1] + 1) * 127.5, clip_value_min = 0., clip_value_max = 255.), dtype = tf.uint8);
      fake_A = tf.cast(tf.clip_by_value((outputs[7] + 1) * 127.5, clip_value_min = 0., clip_value_max = 255.), dtype = tf.uint8);
      with log.as_default():
        tf.summary.scalar('generator A loss', avg_ga_loss.result(), step = optimizerGA.iterations);
        tf.summary.scalar('generator B loss', avg_gb_loss.result(), step = optimizerGB.iterations);
        tf.summary.scalar('discriminator A loss', avg_da_loss.result(), step = optimizerDA.iterations);
        tf.summary.scalar('discriminator B loss', avg_db_loss.result(), step = optimizerDB.iterations);
        tf.summary.image('real A', real_A, step = optimizerGA.iterations);
        tf.summary.image('fake B', fake_B, step = optimizerGA.iterations);
        tf.summary.image('real B', real_B, step = optimizerGA.iterations);
        tf.summary.image('fake A', fake_A, step = optimizerGA.iterations);
      print('Step #%d GA Loss: %.6f GB Loss: %.6f DA Loss: %.6f DB Loss: %.6f lr: %.6f' % \
            (optimizerGA.iterations, avg_ga_loss.result(), avg_gb_loss.result(), avg_da_loss.result(), avg_db_loss.result(), \
            optimizerGA._hyper['learning_rate'](optimizerGA.iterations)));
      avg_ga_loss.reset_states();
      avg_gb_loss.reset_states();
      avg_da_loss.reset_states();
      avg_db_loss.reset_states();
    if tf.equal(optimizerGA.iterations % 10000, 0):
      # save model
      checkpoint.save(os.path.join('checkpoints', 'ckpt'));
    if GA_loss < 0.01 and GB_loss < 0.01 and DA_loss < 0.01 and DB_loss < 0.01: break;
  # save the network structure with weights
  if False == os.path.exists('models'): os.mkdir('models');
  cycleGAN.GA.save(os.path.join('models', 'GA.h5'));
  cycleGAN.GB.save(os.path.join('models', 'GB.h5'));
  cycleGAN.DA.save(os.path.join('models', 'DA.h5'));
  cycleGAN.DB.save(os.path.join('models', 'DB.h5'));

if __name__ == "__main__":
    
  assert True == tf.executing_eagerly();
  main();
