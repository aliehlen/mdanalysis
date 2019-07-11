# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
#
# MDAnalysis --- https://www.mdanalysis.org
# Copyright (c) 2006-2017 The MDAnalysis Development Team and contributors
# (see the file AUTHORS for the full list of names)
#
# Released under the GNU Public Licence, v2 or any higher version
#
# Please cite your use of MDAnalysis in published work:
#
# R. J. Gowers, M. Linke, J. Barnoud, T. J. E. Reddy, M. N. Melo, S. L. Seyler,
# D. L. Dotson, J. Domanski, S. Buchoux, I. M. Kenney, and O. Beckstein.
# MDAnalysis: A Python package for the rapid analysis of molecular dynamics
# simulations. In S. Benthall and S. Rostrup editors, Proceedings of the 15th
# Python in Science Conference, pages 102-109, Austin, TX, 2016. SciPy.
# doi: 10.25080/majora-629e541a-00e
#
# N. Michaud-Agrawal, E. J. Denning, T. B. Woolf, and O. Beckstein.
# MDAnalysis: A Toolkit for the Analysis of Molecular Dynamics Simulations.
# J. Comput. Chem. 32 (2011), 2319--2327, doi:10.1002/jcc.21787
#
"""GSD trajectory reader  --- :mod:`MDAnalysis.coordinates.GSD`
============================================================

Class to read the GSD trajectory, output of `HOOMD-blue`_. The GSD format
specifies both the topology and the trajectory of the particles in the
simulation. The topology is read by the
:class:`~MDAnalysis.topology.GSDParser.GSDParser` class.

The GSD format was developed having in mind the possibility of changing number
of particles, particle types, particle identities and changing topology.
Currently this class has limited functionality, due to the fact that the number
of particles and the topology are kept fixed in most MD simulations. The user
will get an error only if at any time step the number of particles is detected
to be different to the one that was set at the first time step. No check on
changes in particle identity or topology is currently implemented.

.. _`HOOMD-blue`: http://codeblue.umich.edu/hoomd-blue/index.html

Classes
-------

.. autoclass:: GSDReader
   :inherited-members:

"""
from __future__ import absolute_import, division

import numpy as np
import os
if os.name != 'nt':
    import gsd.hoomd

from . import base

class GSDReader(base.ReaderBase):
    """Reader for the GSD format.

    """
    format = 'GSD'
    units = {'time': None, 'length': None}

    def __init__(self, filename, **kwargs):
        """
        Parameters
        ----------
        filename : str
            trajectory filename
        **kwargs : dict
            General reader arguments.


        .. versionadded:: 0.17.0
        """
        if os.name == 'nt':
            raise NotImplementedError("GSD format not supported on Windows")

        super(GSDReader, self).__init__(filename, **kwargs)
        self.filename = filename
        self.open_trajectory()
        self.n_atoms = self._file[0].particles.N
        self.ts = self._Timestep(self.n_atoms, **self._ts_kwargs)
        self._read_next_timestep()

    def open_trajectory(self) :
        """opens the trajectory file using gsd.hoomd module"""
        self._frame = -1
        self._file = gsd.hoomd.open(self.filename,mode='rb')

    def close(self):
        """close reader"""
        self._file.file.close()

    @property
    def n_frames(self):
        """number of frames in trajectory"""
        return len(self._file)

    def _reopen(self):
        """reopen trajectory"""
        self.close()
        self.open_trajectory()

    def _read_frame(self, frame):
        try :
            myframe = self._file[frame]
        except IndexError :
            raise IOError

        # set frame number
        self._frame = frame

        # sets the Timestep object
        self.ts.frame = frame
        self.ts.data['step'] = myframe.configuration.step

        # set frame box dimensions
        self.ts.dimensions = myframe.configuration.box
        
        # this is not how you get angles, according to the hoomd docs
        # https://hoomd-blue.readthedocs.io/en/stable/box.html?highlight=box%20triclinic%20
#        for i in range(3,6) :
#            self.ts.dimensions[i] = np.arccos(self.ts.dimensions[i]) * 180.0 / np.pi
        
        self.ts.tilt_factors = self.ts.dimensions[3:6].copy()
        
        a1a2 = self.ts.dimensions[3] / \
                np.sqrt(1 + self.ts.dimensions[3]**2)
        a1a3 = self.ts.dimensions[4] / \
                np.sqrt(1 + self.ts.dimensions[4]**2 + self.ts.dimensions[5]**2)
        a2a3 = (self.ts.dimensions[3]*self.ts.dimensions[4] + self.ts.dimensions[5] )/ \
                (np.sqrt(1 + self.ts.dimensions[3]**2)* \
                 np.sqrt(1 + self.ts.dimensions[4]**2 + self.ts.dimensions[5]**2))
                
        a1a2 = np.arccos(a1a2) * 180.0 / np.pi # gamma
        a1a3 = np.arccos(a1a3) * 180.0 / np.pi # beta
        a2a3 = np.arccos(a2a3) * 180.0 / np.pi # alpha   
        
        self.ts.dimensions[3] = a2a3
        self.ts.dimensions[4] = a1a3
        self.ts.dimensions[5] = a1a2
        
                 
        # set particle positions
        frame_positions = myframe.particles.position
        n_atoms_now = frame_positions.shape[0]
        if n_atoms_now != self.n_atoms :
            raise ValueError("Frame %d has %d atoms but the initial frame has %d"
                " atoms. MDAnalysis in unable to deal with variable"
                " topology!"%(frame, n_atoms_now, self.n_atoms))
        else :
            self.ts.positions = frame_positions
            
        # AE hack
        self.ts.images = myframe.particles.image
        self.ts.velocities = myframe.particles.velocity
            
        return self.ts

    def _read_next_timestep(self) :
        """read next frame in trajectory"""
        return self._read_frame(self._frame + 1)
