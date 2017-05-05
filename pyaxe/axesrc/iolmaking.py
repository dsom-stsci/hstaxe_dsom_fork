from __future__ import (absolute_import, unicode_literals, division,
                        print_function)

import os
import math
from stwcs.wcsutil import HSTWCS
from astropy.io import fits
from stsci.tools import fileutil

from ..axeerror import aXeError
from axe import axe_asciidata
from .. import axeutils
from . import axeiol

class ProjectionList:
    """
    The central class for the new lists that are going
    to be generated by projecting out positions from a
    multidrizzled image.
    """
    def __init__(self, header_name, dim_info):

        """
        Parameters
        ----------
        header_name: str
            the input image description in the header of the
            multidrizzled image
        dim_info: str
            information on extra pixel rows/columns to be added
            to the 'natural' image size

        Returns
        -------
        Nothing

        Notes:
        ------
        This init-method extract all necessary instance date
        from the input image expression in the header of the
        multidrizzled data. Also the dimensions of the input image
        are determined, and with together with the input parameter
        the x/y-min/max of the area allowed in the IOL is defined.
        """
        # store the input name
        self.header_name = header_name

        # get the information related to the IOL
        self.iol_info = self._get_iol_info(header_name)

        # make sure the fits file exists
        if not os.path.isfile(self.iol_info['fits']):
            err_msg = ("IOLPREP: File {0:s} does not exist!"
                       .format(self.iol_info['fits']))
            raise aXeError(err_msg)

        # determine the IOL name
        self.iol_name = self._get_iol_name(self.iol_info)

        # compute the dimension information
        self.dim_info = self._compute_diminfo(self.iol_info, dim_info)

    def _get_iol_info(self, header_name):
        """Get all info on the extension"""
        # create an empty dict
        iol_info = {}

        # get the bracket information
        exte_str = header_name.split('.fits')[1]

        # get the inside of the brackets
        exte_data = exte_str[1:len(exte_str)-1]

        # collect fits name, extension name and extension
        # version in the dictionary
        iol_info['root'] = header_name.split('.fits')[0]
        iol_info['fits'] = header_name.split('.fits')[0] + '.fits'
        iol_info['ext_nam'] = exte_data.split(',')[0]
        iol_info['ext_ver'] = int(exte_data.split(',')[1])

        # return the extension information
        return iol_info

    def _get_iol_name(self, iol_info):
        """Compose the IOL name"""
        # compose the IOL name
        iol_name = '%s_%i.cat' % (iol_info['root'], iol_info['ext_ver'])

        # return the name
        return iol_name

    def _compute_diminfo(self, iol_info, dim_info):
        """Compute the absolute dimension information"""
        # create an empty list
        abs_dims = []

        # the the dimension of the input image
        indims = self._get_indims(iol_info)
        # possible add rows/columns on either side.
        # the '0.5' generally have to be there
        # given an image with 1000 pix, SExtractor
        # can distribute object position in [0.5, 1000.5]
        abs_dims.append(0.5-dim_info[0])
        abs_dims.append(0.5+dim_info[1]+indims[0])
        abs_dims.append(0.5-dim_info[2])
        abs_dims.append(0.5+dim_info[3]+indims[1])

        # return the result
        return abs_dims

    def _get_indims(self, iol_info):
        """ """
        # make sure the fits image exists
        if not os.path.isfile(iol_info['fits']):
            err_msg = 'Image: ' + iol_info['fits'] + ' does not exist!'
            raise aXeError(err_msg)

        # open the image and get the header
        in_img = fits.open(iol_info['fits'], 'readonly')
        in_head = in_img[iol_info['ext_nam'], iol_info['ext_ver']].header

        # extract the keywords for the image size from
        # the header
        dims = [in_head['NAXIS1'], in_head['NAXIS2']]

        # close the image
        in_img.close()

        # return the list with the image dimension
        return dims

    def _get_coeff_name(self, iol_info):
        """Compose the coefficient filename"""
        # set default number
        chipnum = 1

        # open the image and get the header
        in_img = fits.open(iol_info['fits'], 'readonly')

        # ACS:
        # check for the chip number
        if ('CCDCHIP' in in_img[iol_info['ext_nam'],
                                iol_info['ext_ver']].header):
            chipnum = in_img[iol_info['ext_nam'],
                             iol_info['ext_ver']].header['CCDCHIP']
        # NICMOS:
        elif ('CAMERA' in in_img[0].header):
            chipnum = in_img[0].header['CAMERA']

        # close the fits
        in_img.close()

        # compose the coefficient name
        coeffname = "{0:s}_coeffs{1:d}.dat".format((iol_info['root'], chipnum))

        # return the number
        return coeffname

    def make_grismcat(self,
                      data_name,
                      data_angle,
                      grism_cat,
                      mdrizzle_image,
                      odd_signs=None):
        """Make the grism catalog

        The method creates a new input object list. The positional
        information on objects in a multidrizzled image are projected
        back into the coordinate system of one nput image.
        A selection is done on the basis of the projected coordinates,
        and the selected objects are stored to a new IOL file

        Parameters
        ----------
        data_name: str
            filename of the position data
        data_angle: str
            filename of the displaced positions
        grism_cat: str
            efernece to the axecat object
        mdrizzle_image: str
            name of the drizzled image

        Returns
        -------
            Nothing
        """
        print("\n >>>> Working on Input Object List: {0:s} >>>>\n"
              .format(self.iol_name))

        # use HSTWCS instead for the astrodrizzle image
        # read in the data_name file
        # awtran gives back this format:
        # all_out.append("%10.3f %10.3f %10.3f %10.3f" % (xin,yin,xout,yout))

        hstimage = HSTWCS(mdrizzle_image, ext=1)
        datanamefile = open(data_name, 'r')
        datapoints = datanamefile.readlines()
        data = [list(map(float, line.split())) for line in datapoints]

        # trans points are now in ra and dec from mdrizzle_image
        skypoints = hstimage.all_pix2world(data, 1)

        # now translate to new image pixel points
        newhstimage = HSTWCS(self.header_name)
        trans_pts = newhstimage.all_world2pix(skypoints[:, 0],
                                              skypoints[:, 1], 1)
        # pix2sky returns (2,len) array of points
        dir_pts = list()
        for i in range(0, len(trans_pts[0])):
            dir_pts.append("{10.8g} {10.8g} {10.8g} {10.8g}"
                           .format(trans_pts[0][i],
                                   trans_pts[1][i],
                                   skypoints[i, 0],
                                   skypoints[i, 1]))

        # now the same for the ang file points
        angfile = open(data_angle, 'r')
        angpoints = angfile.readlines()
        data = [list(map(float, line.split())) for line in angpoints]

        ang_pts = list()
        for i in range(0, len(trans_pts[0])):
            ang_pts.append("{10.8g} {10.8g} {10.8g} {10.8g}"
                           .format(data[i][0],
                                   data[i][1],
                                   trans_pts[0][i],
                                   trans_pts[1][i]))
        # start the reverse index;
        # iterate over all objects
        r_index = len(dir_pts) - 1

        for index in range(grism_cat.nrows):
            # extract the projected object positions
            x_ori = float(dir_pts[r_index].split()[0])
            y_ori = float(dir_pts[r_index].split()[1])

            # check whether the object position is
            # range to be stored
            if x_ori >= self.dim_info[0] and x_ori <= self.dim_info[1] and \
               y_ori >= self.dim_info[2] and y_ori <= self.dim_info[3]:

                # extract the displaced projected position
                x_ang = float(ang_pts[r_index].split()[0])
                y_ang = float(ang_pts[r_index].split()[1])

                # compute the new object angle
                dx = x_ang-x_ori
                dy = y_ang-y_ori
                angle = math.atan2(dy, dx)/math.pi*180.0

                # fill in the new position and angle
                grism_cat['X_IMAGE'][r_index] = x_ori
                grism_cat['Y_IMAGE'][r_index] = y_ori
                grism_cat['THETA_IMAGE'][r_index] = angle

            # delete outside entries
            else:
                grism_cat.delete(r_index)

            # decrease the reverse index
            r_index -= 1

        # save the new IOL
        grism_cat.writeto(self.iol_name)

        print()
        print(" >>>> Catalog: {0:s} written with {1:s} entries.>>>> "
              .format(self.iol_name, grism_cat.nrows))
        print()


class IOL_Maker:
    """Central class to take the input and to create Input Object Lists

    for the list of images extracted from the header of the
    multidrizzled image.
    """
    def __init__(self, mdrizzle_image, input_cat,  dim_term):
        """
        Parameters
        ----------
        mdrizzle_image: str
            the name of the multidrizzled image
        input_cat: str
            the name of the input catalogue
        dim_info:
            description of the additional rows/column for the
            Input Object Lists

        Returns
        -------
        Nothing

        Notes
        -----
        The class data is set. While doing that, basic checks
        on the input is done. The existence of the images is
        checked, also the data type of the various real
        or integer numbers.
        """
        self.iol_list = []

        # check whether the multidrizzled image exists,
        # store the name if it exists
        if not os.path.isfile(mdrizzle_image):
            err_msg = "File: {0:s} does not exist!".format(mdrizzle_image)
            raise aXeError(err_msg)
        else:
            self.mdrizzle_image = mdrizzle_image

        # check whether the input catalogue exists,
        # store the name if it exists
        if not os.path.isfile(input_cat):
            err_msg = 'File: ' + input_cat + ' does not exist!'
            raise aXeError(err_msg)
        else:
            self.input_cat = input_cat

        # resolve and get the dimension information
        self.dim_info = self._get_dimension_info(dim_term)

        # create the list of Input Object Instances
        self.iol_list = self._fill_iollist(self.mdrizzle_image)
        pstring = ("IOLPREP: {0:s} Input Object Lists will be created!"
                   .format(str(len(self.iol_list))))
        print("\n{0:s}\n".format(pstring))

    def _get_dimension_info(self, dimension_term):
        """Get the dimension information"""
        # initialize the array
        dim_info = []

        # check the dimension input
        dim_entries = dimension_term.split(',')

        # is the number of items correct?
        if len(dim_entries) != 4:
            err_msg = ("There must be 4 entries in the term: {0:s},"
                       "not {1:d}!".format(dimension_term, len(dim_entries)))
            raise aXeError(err_msg)

        # check whether each item is an integer
        for item in dim_entries:
            if self._toInt(item.strip()) is None:
                raise aXeError("Item: {} must be integer!".format(item))
            # store the item
            dim_info.append(self._toInt(item.strip()))

        # return the array
        return dim_info

    def _make_data_files(self, master_cat, data_name, data_angle):
        """create temp file with object locations
        Parameters
        ----------
        master_cat: str
            the instance of the input catalogue
        data_name: str
            the name of the positions file
        data_angle: str
            the name of the displaced posiitons file

        Returns
        -------
        Nothing

        Notes
        -----
        This method creates two teporary files with the positions
        and the displaced positions of the objects in the input
        catalogue. The temporary files are needed to work
        with the task 'tran' on them as input.
        The displaced positions are used to recalculate
        the object angle in the projected coordinate system
        """

        # create two empty tables
        data_tab = axe_asciidata.create(2, master_cat.nrows)
        angle_tab = axe_asciidata.create(2, master_cat.nrows)

        # go over all rows
        for index in range(master_cat.nrows):

            # get position and orientation
            x_pos = master_cat['X_IMAGE'][index]
            y_pos = master_cat['Y_IMAGE'][index]
            theta = master_cat['THETA_IMAGE'][index]

            # compute shift position
            x_shift = x_pos + 10.0 * math.cos(theta / 180.0 * math.pi)
            y_shift = y_pos + 10.0 * math.sin(theta / 180.0 * math.pi)

            # fill the positons in the table
            data_tab[0][index] = x_pos
            data_tab[1][index] = y_pos

            # fillthe shifted positions in table
            angle_tab[0][index] = x_shift
            angle_tab[1][index] = y_shift

        # write the two lists to disk
        data_tab.writeto(data_name)
        angle_tab.writeto(data_angle)

        self.data_name = data_name
        self.data_angle = data_angle

    def _fill_iollist(self, mdrizzle_image):
        """Derive the names for the input parameters

        Parameters
        ----------
        mdrizzle_image: str
            the name of the image

        Returns
        -------
        iolists: list
            the list of new IOL instances

        Notes
        -----
        The method derives the names for the input
        images from the header of the multidrizzled images
        and then creates an Input Object List instance
        for each input image. The list with the
        IOL instances is then returned.
        """
        iolists = []

        # determine the number of iput images
        n_iols = self._get_niol(mdrizzle_image)

        mdrizzle_img = fits.open(mdrizzle_image, 'readonly')
        mdrizzle_head = mdrizzle_img[0].header

        # for each input image
        for index in range(1, n_iols+1):

            # extract the name
            keyname = 'D%03iDATA' % (index)

            # create a new IOl instance at the end of the list
            iolists.append(ProjectionList(mdrizzle_head[keyname],
                           self.dim_info))

        # close the fits image
        mdrizzle_img.close()

        # return the fluxcube list
        return iolists

    def _get_niol(self, mdrizzle_image):
        """Return the number of input images from the header
        Parameters
        ----------
        mdrizzle_image: str
            the name of the multidrizzled grism image

        Returns
        -------
        ID: int
            The number of input images

        Notes
        -----
        The method looks in the header of the multidrizzled image
        for the name of the input images used in the multidrizzle
        process. This number is returned
        """
        # open the fits file and get the header
        mdrizzle_img = fits.open(mdrizzle_image, 'readonly')
        mdrizzle_head = mdrizzle_img[0].header

        # create the keyname for the first input image
        ID = 1
        keyname = "D{0:03d}DATA".format(ID)

        # create the keyname for subsequent input images
        # and continue until the keynames do not exist
        while keyname in mdrizzle_head:
            ID = ID+1
            keyname = "D{0:03d}DATA".format(ID)

        # close the multidrizzled image
        mdrizzle_img.close()

        # correct the number
        ID = ID-1

        # return the number
        return ID

    def _toFloat(self, input):
        """check if the expression is a float
        Parameters
        ----------
        input: str
            the string to check

        Returns
        -------
        fret: float
            the float representation of the input

        Notes
        -----
        The module checks whether an expression is a
        float or not. The float representation of the
        expresion or None is returned
        """
        try:
            fret = float(input)
        except ValueError:
            return None
        return fret

    def _toInt(self, input):
        """Check for integer, return int or None
        Input:
            input - the string to check

        Return:
            iret - the integer representation of the input

        Description:
            The module checks whether an expression is an
            integer or not. The integer representation of the
            expression or None is returned
        """
        try:
            iret = int(input)
        except ValueError:
            return None
        return iret

    def _make_odd_signs(self):
        """Determine odd number of pixels"""
        # get the x-and y-dimension
        ftype = fileutil.isFits(self.mdrizzle_image)
        if ftype[1] is "mef":
            ext = 1
        else:
            ext = 0
        fits_im = fits.open(self.mdrizzle_image, 'readonly')
        x_dim = fits_im[ext].data.shape[1]
        y_dim = fits_im[ext].data.shape[0]
        fits_im.close()

        # return a tuple with odd-signs for x and y
        return (math.fmod(float(x_dim), 2.0) > 0.0,
                (math.fmod(float(y_dim), 2.0) > 0.0))

    def run(self):
        """actually create the Input Object Lists

        This method is responsible to actually create the
        Input Object Lists. Other internal methods as well as
        methods of other classes are successively
        called to create the Input Object Lists associated to the
        input images listed in the header of the
        multidrizzled image.
        """

        # determine odd dimensions
        # Note: this is only necessary
        #       as long as there are two different
        #       flavors in pydrizzle and iraf.drizzle
        odd_signs = self._make_odd_signs()

        # load the input catalogue twice.
        # once as a reference for the input
        # and once as a template to build
        # and save the new IOL's from
        master_cat = axeiol.InputObjectList(self.input_cat)
        grism_cat = axeiol.InputObjectList(self.input_cat)

        # name and create the two temporary files
        # with object positions. the task 'tran'
        # will then work on the basis of this
        # files
        data_name = axeutils.get_random_filename('', '.dat')
        data_angle = axeutils.get_random_filename('', '.dat')

        if os.path.isfile(data_name):
            os.unlink(data_name)
        if os.path.isfile(data_angle):
            os.unlink(data_angle)
            self._make_data_files(master_cat, data_name, data_angle)

        # create the new Input Object Lists
        for iol in self.iol_list:
            # load the entire catalogue again
            grism_cat = axeiol.InputObjectList(self.input_cat)

            # make a new IOL
            iol.make_grismcat(data_name,
                              data_angle,
                              grism_cat,
                              self.mdrizzle_image,
                              odd_signs)

        # delete the temporary files
        if os.path.isfile(data_name):
            os.unlink(data_name)
        if os.path.isfile(data_angle):
            os.unlink(data_angle)
