#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2010 Radim Rehurek <radimrehurek@seznam.cz>
# Licensed under the GNU LGPL v2.1 - http://www.gnu.org/licenses/lgpl.html

"""
USAGE: %(program)s

    Worker ("slave") process used in computing distributed LSI. Run this script \
on every node in your cluster. If you wish, you may even run it multiple times \
on a single machine, to make better use of multiple cores (just beware that \
memory footprint increases accordingly).

Example: python lsi_worker.py
"""


from __future__ import with_statement
import os, sys, logging
import threading

import Pyro
import Pyro.config

from gensim.models import lsimodel
from gensim import utils

logger = logging.getLogger('lsi_worker')
logger.setLevel(logging.DEBUG)



class Worker(object):
    def __init__(self):
        self.model = None

    
    def initialize(self, myid, dispatcher, **model_params):
        self.lock_update = threading.Lock()
        self.jobsdone = 0 # how many jobs has this worker completed?
        self.myid = myid # id of this worker in the dispatcher; just a convenience var for easy access/logging TODO remove?
        self.dispatcher = dispatcher
        logger.info("initializing worker #%s" % myid)
        self.model = lsimodel.LsiModel(**model_params)
        self._exit = False
    
    
    def requestjob(self):
        """
        Request jobs from the dispatcher in an infinite loop. The requests are 
        blocking, so if there are no jobs available, the thread will wait.  
        
        Once the job is finished, the dispatcher is notified that it should collect
        the results, broadcast them to other workers etc., and eventually tell
        this worker to request another job by calling this function again.
        """
        if self.model is None:
            raise RuntimeError("worker must be initialized before receiving jobs")
        job = self.dispatcher.getjob(self.myid) # blocks until a new job is available from the dispatcher
        logger.debug("worker #%s received job #%i" % (self.myid, self.jobsdone))
        self.processjob(job)
        self.dispatcher.jobdone(self.myid)


    @utils.synchronous('lock_update')
    def processjob(self, job):
        self.model.add_documents(job, update_projection = False)
        self.jobsdone += 1


    @utils.synchronous('lock_update')
    def getstate(self):
        logger.info("worker #%i returning its state after %s jobs" % 
                    (self.myid, self.jobsdone))
        assert isinstance(self.model.projection, lsimodel.Projection)
        return self.model.projection
#endclass Worker



def main():
    Pyro.config.HOST = utils.get_my_ip()
    
    with Pyro.naming.locateNS() as ns:
        with Pyro.core.Daemon() as daemon:
            worker = Worker()
            uri = daemon.register(worker)
            name = 'gensim.worker.' + str(uri)
            ns.remove(name)
            ns.register(name, uri)
            logger.info("worker is ready at URI %s" % uri)
            daemon.requestLoop()



if __name__ == '__main__':
    logging.basicConfig(format = '%(asctime)s : %(levelname)s : %(message)s')
    logger.info("running %s" % " ".join(sys.argv))

    program = os.path.basename(sys.argv[0])
    # make sure we have enough cmd line parameters
    if len(sys.argv) < 1:
        print globals()["__doc__"] % locals()
        sys.exit(1)
    
    main()
    
    logger.info("finished running %s" % program)