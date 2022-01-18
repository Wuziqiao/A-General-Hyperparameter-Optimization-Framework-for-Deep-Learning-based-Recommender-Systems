from engine import setup_args, Engine


if __name__ == '__main__':
    parser = setup_args()
    parser.set_defaults(
        alias='test',
        tensorboard='./tmp/runs/ml1m/MF/fixed/',
        regularizer = 'fixed',
        ##########
        ## data ##
        ##########
        reconstruct_data=True,
        data_type='ml1m-mf',
        data_path='./data/ml-1m/ratings.dat',
        load_in_queue=False,
        filtered_data_path='./tmp/data/ml1m-mf-filter_u0i0.dat',
        eval_res_path='./tmp/res/ml1m/{alias}/{epoch_idx}.csv',
        item_freq_threshold_lb=0,
        user_freq_threshold_lb=0,
        freq_threshold_ub=int(1e9),
        metric_topk=50,
        ######################
        ## train/test split ##
        ######################
        train_test_split='lro',
        test_ratio=0.2,
        valid_ratio=0.25,
        ##########################
        ## Devices & Efficiency ##
        ##########################
        use_cuda=True,
        log_interval=1,  # 816
        eval_interval=10, # 10 epochs between 2 evaluations
        multi_cpu_train=False,
        num_workers_train=1,
        multi_cpu_valid=False,
        num_workers_valid=1,
        multi_cpu_test=True,
        num_workers_test=1,
        device_ids_test=[8],
        device_id=8,
        batch_size_train=1024,
        batch_size_valid=1024,
        batch_size_test=1024,
        num_negatives=1,
        ###########
        ## Model ##
        ###########
        fixed_lambda_candidate=[1e-3],#-1, -3,-5,-7,-9, 0
        latent_dim=128,
        mf_lr=0.008,
        mf_optimizer='AdaMod',
        mf_amsgrad=False,
        mf_eps=1e-8,
        mf_l2_regularization=0,
        mf_betas=(0.9, 0.999),
        mf_grad_clip=100,  # 0.1
        mf_lr_exp_decay=1,
        lambda_update_interval=1,
    )

    opt = parser.parse_args(args=[])
    opt = vars(opt)

    # rename alias
    opt['alias'] = opt['alias'] + 'Top{}_{}_{}_lambda{}_K{}_' \
                   'bsz{}_mflr_{}_mfoptim{}'.format(
        opt['metric_topk'],
        opt['alias'],
        opt['regularizer'],
        opt['fixed_lambda_candidate'],
        opt['latent_dim'],
        opt['batch_size_train'],
        opt['mf_lr'],
        opt['mf_optimizer'])

    engine = Engine(opt)
    engine.train()
