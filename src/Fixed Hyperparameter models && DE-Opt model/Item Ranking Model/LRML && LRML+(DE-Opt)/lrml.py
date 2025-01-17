#!/usr/bin/env python
"""Implementation of Latent Relational Metric Learning (LRML)
WWW 2018. Authors - Yi Tay, Luu Anh Tuan, Siu Cheung Hui
"""

import tensorflow.compat.v1 as tf
import time
import numpy as np

from RankingMetrics import *

__author__ = "Yi Tay"
__copyright__ = "Copyright 2018, The DeepRec Project"

__license__ = "GPL"
__version__ = "1.0.0"
__maintainer__ = "Yi Tay"
__email__ = "ytay017@gmail.com"
__status__ = "Development"


class LRML():
    """ This is a reference implementation of the LRML model
    proposed in WWW'18.
    Note: This was mainly adapted for the DeepRec repository
    and is copied from the first author's
    private code repository. This has NOT undergone sanity checks.
    """

    def __init__(self, sess, num_user, num_item, learning_rate,
                 reg_rate, epoch=500, batch_size=4096,
                 verbose=False, T=5, display_step=1000, mode=1,
                 copy_relations=True, dist='L1', num_mem=100, individual_num=5, lr_min=0.0001, lr_max=0.01, reg_rate_min=0.001, reg_rate_max=0.1,
                 max_ndcg10_DE=-1, min_round=0, delay_round=5, total_round=0):
        """ This model takes after the CML structure implemented by Shuai.
        There are several new hyperparameters introduced which are explained
        as follows:
        Args:
            mode:`int`.1 or 2. varies the attention computation.
                    2 corresponds to the implementation in the paper.
                    But 1 seems to produce better results.
            copy_relations: `bool`. Reuse relation vector for negative sample.
            dist: `str`. L1 or L2. Use L1 or L2 distance.
            num_mem: `int`. Controls the number of memory rows.
        """
        self.learning_rate = learning_rate
        self.epochs = epoch
        self.batch_size = batch_size
        self.reg_rate = reg_rate
        self.sess = sess
        self.num_user = num_user
        self.num_item = num_item
        self.verbose = verbose
        self.T = T
        self.mode = mode
        self.display_step = display_step
        # self.init = 1 / (num_factor ** 0.5)
        self.num_mem = num_mem
        self.copy_relations = copy_relations
        self.dist = dist
        self.individual_num = individual_num
        self.lr_min = lr_min
        self.lr_max = lr_max
        self.reg_rate_min = reg_rate_min
        self.reg_rate_max = reg_rate_max
        self.max_ndcg10_DE = max_ndcg10_DE
        self.min_round = min_round
        self.ndcg_10 = -1
        self.ndcg_20 = -1
        self.recall_10 = -1
        self.recall_20 = -1

        self.overTime = 0
        self.delay_round = delay_round
        self.total_round = total_round
        print("LRML.")

    def lram(self, a, b,
             reuse=None, initializer=None, k=10, relation=None):
        """ Generates relation given user (a) and item(b)
        """
        with tf.variable_scope('lrml', reuse=reuse) as scope:
            if (relation is None):
                _dim = a.get_shape().as_list()[1]
                key_matrix = tf.get_variable('key_matrix', [_dim, k],
                                             initializer=initializer)
                memories = tf.get_variable('memory', [_dim, k],
                                           initializer=initializer)
                user_item_key = a * b
                key_attention = tf.matmul(user_item_key, key_matrix)
                key_attention = tf.nn.softmax(key_attention)  # bsz x k
                if (self.mode == 1):
                    relation = tf.matmul(key_attention, memories)
                elif (self.mode == 2):
                    key_attention = tf.expand_dims(key_attention, 1)
                    relation = key_attention * memories
                    relation = tf.reduce_sum(relation, 2)
        return relation

    def build_network(self, num_factor=100, margin=0.5, norm_clip_value=1):
        """ Main computational graph
        """
        # stddev initialize
        init = 1 / (num_factor ** 0.5)

        self.user_id = tf.placeholder(dtype=tf.int32, shape=[None], name='user_id')
        self.item_id = tf.placeholder(dtype=tf.int32, shape=[None], name='item_id')
        self.neg_item_id = tf.placeholder(dtype=tf.int32, shape=[None], name='neg_item_id')
        self.keep_rate = tf.placeholder(tf.float32)

        self.P = tf.Variable(tf.random_normal([self.num_user, num_factor], stddev=init), dtype=tf.float32)
        self.Q = tf.Variable(tf.random_normal([self.num_item, num_factor], stddev=init), dtype=tf.float32)

        user_embedding = tf.nn.embedding_lookup(self.P, self.user_id)
        item_embedding = tf.nn.embedding_lookup(self.Q, self.item_id)
        neg_item_embedding = tf.nn.embedding_lookup(self.Q, self.neg_item_id)

        selected_memory = self.lram(user_embedding, item_embedding,
                                    reuse=tf.AUTO_REUSE,
                                    initializer=tf.random_normal_initializer(init),
                                    k=self.num_mem)
        if (self.copy_relations == False):
            selected_memory_neg = self.lram(user_embedding, neg_item_embedding,
                                            reuse=True,
                                            initializer=tf.random_normal_initializer(init),
                                            k=self.num_mem)
        else:
            selected_memory_neg = selected_memory

        energy_pos = item_embedding - (user_embedding + selected_memory)
        energy_neg = neg_item_embedding - (user_embedding + selected_memory_neg)

        if (self.dist == 'L2'):
            pos_dist = tf.sqrt(tf.reduce_sum(tf.square(energy_pos), 1) + 1E-3)
            neg_dist = tf.sqrt(tf.reduce_sum(tf.square(energy_neg), 1) + 1E-3)
        elif (self.dist == 'L1'):
            pos_dist = tf.reduce_sum(tf.abs(energy_pos), 1)
            neg_dist = tf.reduce_sum(tf.abs(energy_neg), 1)

        self.pred_distance = pos_dist
        self.pred_distance_neg = neg_dist

        # self.loss = tf.reduce_sum(tf.maximum(self.pred_distance - self.pred_distance_neg + margin, 0))
        #
        # self.optimizer = tf.train.GradientDescentOptimizer(self.learning_rate).minimize(self.loss, var_list=[P, Q])
        self.clip_P = tf.assign(self.P, tf.clip_by_norm(self.P, norm_clip_value, axes=[1]))
        self.clip_Q = tf.assign(self.Q, tf.clip_by_norm(self.Q, norm_clip_value, axes=[1]))

        return self

    def prepare_data(self, train_data, validation_data,test_data):
        '''
        You must prepare the data before train and test the model
        :param train_data:
        :param test_data:
        :return:
        '''
        t = train_data.tocoo()
        self.user = t.row.reshape(-1)
        self.item = t.col.reshape(-1)
        self.num_training = len(self.item)
        print(self.num_training)
        self.validation_data = validation_data
        self.test_data = test_data
        self.total_batch = int(self.num_training / self.batch_size)
        self.neg_items = self._get_neg_items(train_data.tocsr())
        self.validation_users = set([u for u in self.validation_data.keys() if len(self.validation_data[u]) > 0])
        self.test_users = set([u for u in self.test_data.keys() if len(self.test_data[u]) > 0])
        print(self.total_batch)
        print("data preparation finished.")
        return self

    def train(self):
        idxs = np.random.permutation(self.num_training)  # shuffled ordering
        user_random = list(self.user[idxs])
        item_random = list(self.item[idxs])
        item_random_neg = []
        for u in user_random:
            neg_i = self.neg_items[u]
            s = np.random.randint(len(neg_i))
            item_random_neg.append(neg_i[s])

        margin = 0.5
        self.loss = tf.reduce_sum(tf.maximum(self.pred_distance - self.pred_distance_neg + margin, 0))

        self.optimizer = tf.train.GradientDescentOptimizer(self.learning_rate).minimize(self.loss, var_list=[self.P, self.Q])

        # train
        for i in range(self.total_batch):
            start_time = time.time()
            batch_user = user_random[i * self.batch_size:(i + 1) * self.batch_size]
            batch_item = item_random[i * self.batch_size:(i + 1) * self.batch_size]
            batch_item_neg = item_random_neg[i * self.batch_size:(i + 1) * self.batch_size]

            _, loss, _, _ = self.sess.run((self.optimizer, self.loss, self.clip_P, self.clip_Q),
                                          feed_dict={self.user_id: batch_user,
                                                     self.item_id: batch_item,
                                                     self.neg_item_id: batch_item_neg,
                                                     self.keep_rate: 0.98})

            if i % self.display_step == 0:
                if self.verbose:
                    print("Index: %04d; cost= %.9f" % (i + 1, np.mean(loss)))
                    print("one iteration: %s seconds." % (time.time() - start_time))

    def test(self):
        Recall_5, Recall_10, ndcg, ndcg_5, ndcg_10 = evaluate_test(self)
        return Recall_5, Recall_10, ndcg, ndcg_5, ndcg_10

    def validation(self):
        Recall_5, Recall_10, ndcg, ndcg_5, ndcg_10 = evaluate_validation(self)
        return Recall_5, Recall_10, ndcg, ndcg_5, ndcg_10

    def execute(self, train_data, validation_data, test_data):
        print("参数设置： ", 'learning_rate: %.6f' % (self.learning_rate), ' ;reg_rate: %.6f' % (self.reg_rate))
        self.prepare_data(train_data, validation_data, test_data)

        init = tf.global_variables_initializer()
        self.sess.run(init)
        startTime = time.time()

        for epoch in range(self.epochs):
            time1 = time.time()
            self.train()
            r10, r20, n, n10, n20 = self.validation()
            curResult = n10
            time2 = time.time()
            if curResult > self.max_ndcg10_DE:
                self.max_ndcg10_DE = curResult
                self.min_round = epoch + 1
            else:
                r10_test, r20_test, n_test, n10_test, n20_test = self.test()
                if n10_test > self.ndcg_10:
                    self.ndcg_10 = n10_test
                    self.ndcg_20 = n20_test
                    self.recall_10 = r10_test
                    self.recall_20 = r20_test
                    self.overTime = time.time()

            if (epoch - self.min_round) >= self.delay_round:
                break

            print("Epoch:%02d: " % (epoch+1), 'ndcg@10: %.6f' % n10, 'recall@10: %.6f' % r10, "  Time: %.2f" % (time2 - time1))


        print("Result on TestSet:", 'n@10:', self.ndcg_10, ' n@20:', self.ndcg_20, ' r@10:', self.recall_10, ' r@20:',
              self.recall_20,
              " Time: %.2f " % (self.overTime - startTime))

    def save(self, path):
        saver = tf.train.Saver()
        saver.save(self.sess, path)

    def predict(self, user_id, item_id):
        return -self.sess.run([self.pred_distance],
                              feed_dict={self.user_id: user_id,
                                         self.item_id: item_id, self.keep_rate: 1})[0]

    def _get_neg_items(self, data):
        all_items = set(np.arange(self.num_item))
        neg_items = {}
        for u in range(self.num_user):
            neg_items[u] = list(all_items - set(data.getrow(u).nonzero()[1]))

        return neg_items
