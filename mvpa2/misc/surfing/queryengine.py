# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the PyMVPA package for the
#   copyright and license terms.
#
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""QueryEngine for querying feature ids based on the surface nodes"""


__docformat__ = 'restructuredtext'

import numpy as np

from mvpa2.base.dataset import AttrDataset
from mvpa2.misc.neighborhood import QueryEngineInterface

from mvpa2.misc.surfing import volgeom, volsurf, surf_voxel_selection
from mvpa2.support.nibabel import surf

if __debug__:
    from mvpa2.base import debug

class SurfaceVerticesQueryEngine(QueryEngineInterface):
    """TODO

    """
    def __init__(self, voxsel, space='voxel_indices', add_fa=None):
        super(SurfaceVerticesQueryEngine, self).__init__()
        self.voxsel = voxsel
        self.space = space
        self._map_voxel_coord = None

        if add_fa is not None:
            if not set(voxsel.sa_labels).issuperset(add_fa):
                raise ValueError(
                    "add_fa should list only those known to voxsel %s"
                    % voxsel)
        self._add_fa = add_fa


    @property
    def ids(self):
        return self.voxsel.keys

    def train(self, dataset):
        vg = self.voxsel.volgeom
        # We are creating a map from big unmasked indices of voxels
        # known to voxsel into the dataset's feature indexes
        self._map_voxel_coord = map_voxel_coord = {}
        for long_i, i in zip(
            vg.ijk2lin(dataset.fa[self.space].value),
            xrange(dataset.nfeatures)):
            if long_i in map_voxel_coord:
                map_voxel_coord[long_i].append(i)
            else:
                map_voxel_coord[long_i] = [i]

    def untrain(self):
        self._map_voxel_coord = None


    def query_byid(self, vertexid):
        """Given a vertex ID give us indices of dataset features (voxels)
        """
        # TODO: make linear_voxel_indices a parameter

        voxel_unmasked_ids = self.voxsel.get(vertexid, 'linear_voxel_indices')

        # map into dataset
        voxel_dataset_ids = sum([self._map_voxel_coord[i]
                                 for i in voxel_unmasked_ids], [])
        if self._add_fa is not None:
            # optionally add additional information from voxsel
            ds = AttrDataset(np.asarray(voxel_dataset_ids)[np.newaxis])
            for n in self._add_fa:
                ds.fa[n] = self.voxsel.get(vertexid, n)
            return ds
        return voxel_dataset_ids


    def query(self, **kwargs):
        raise NotImplemented

def disc_surface_queryengine(radius, volume, white_surf, pial_surf, source_surf=None,
                             source_surf_nodes=None, volume_mask=False, add_fa=None,
                             distance_metric='dijkstra'):

    vg = volgeom.from_any(volume, volume_mask)

    # read surfaces
    white_surf = surf.from_any(white_surf)
    pial_surf = surf.from_any(pial_surf)

    if source_surf is None:
        source_surf = white_surf * .5 + pial_surf * .5
    else:
        source_surf = surf.from_any(source_surf)

    # make a volume surface instance
    vs = volsurf.VolSurf(vg, pial_surf, white_surf)

    # run voxel selection
    voxsel = surf_voxel_selection.voxel_selection(vs, radius, source_surf,
                                            source_surf_nodes,
                                            distance_metric=distance_metric)

    qe = SurfaceVerticesQueryEngine(voxsel, add_fa=add_fa)

    return qe



