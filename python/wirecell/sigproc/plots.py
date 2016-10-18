#!/usr/bin/env python
import units
import response

import numpy
import matplotlib.pyplot as plt


def fine_response(rflist_fine, regions = None, shaped=False):
    '''
    Plot fine response functions
    '''
    if regions is None:
        regions = sorted(set([x.region for x in rflist_fine]))
    nregions = len(regions)
    impacts = sorted(set([x.impact for x in rflist_fine]))
    nimpacts = len(impacts)

    fig, axes = plt.subplots(nregions, 3, sharex=True)

    byplane = response.group_by(rflist_fine, 'plane')

    for iplane, plane_rfs in enumerate(byplane):
        print 'plane %d, %d regions' % (iplane, len(plane_rfs))
        byregion = response.group_by(plane_rfs,'region')

        byregion = [lst for lst in byregion if lst[0].region in regions]

        for iregion, region_rfs in enumerate(byregion):
            region_rfs.sort(key=lambda x: x.impact)
            first = region_rfs[0]

            ax = axes[iregion][iplane]
            ax.set_title('region %d' % (first.region,))
            print "plane=%s, region=%d, impacts: " % (first.plane,first.region),
            for rf in region_rfs:
                if shaped:
                    rf = rf.shaped()
                times = numpy.linspace(*rf.domainls)/units.us
                ax.plot(times, rf.response)
                print "[%f] " % rf.impact,
            print
    
    
def average_shaping(rflist_avg, gain_mVfC=14, shaping=2.0*units.us, nbins=5000):
    '''
    Plot average field responses and with electronics shaping.
    '''
    import electronics
    from scipy.signal import fftconvolve

    byplane = response.group_by(rflist_avg, 'plane')
    nfields = len(byplane[0])
    main_field = [rf for rf in byplane[2] if rf.region == 0][0]
    main_field_sum = numpy.max(numpy.abs(main_field.response))
    main_shaped = main_field.shaped(gain_mVfC, shaping, nbins)
    main_shaped_sum = numpy.max(numpy.abs(main_shaped.response))
    rat = main_shaped_sum / main_field_sum


    fig, axes = plt.subplots(nfields, 3, sharex=True)

    for iplane, plane_frs in enumerate(byplane):
        plane_frs.sort(key=lambda x: x.region)

        for ifr, fr in enumerate(plane_frs):
            ax = axes[ifr][iplane]
            ax.set_title('plane %s, region %d' % (fr.plane, fr.region,))

            sh = fr.shaped(gain_mVfC, shaping, nbins)
            ax.plot(fr.times/units.us, fr.response*rat)
            ax.plot(sh.times/units.us, sh.response)
        
    
    


def electronics():
    '''
    Plot electronics response functions
    '''
    fig, axes = plt.subplots(4,1, sharex=True)

    want_gains = [1.0, 4.7, 7.8, 14.0, 25.0]

    engs = numpy.vectorize(response.electronics_no_gain_scale) # by time
    def engs_maximum(gain, shaping=2.0*units.us):
        resp = engs(numpy.linspace(0,10*units.us, 100), gain, shaping)
        return numpy.max(resp)
    engs_maximum = numpy.vectorize(engs_maximum) # by gain
                     
    gainpar = numpy.linspace(0,300,6000)
    for ishaping, shaping in enumerate([0.5, 1.0, 2.0, 3.0]):
        gain = engs_maximum(gainpar, shaping*units.us)
        slope, inter = numpy.polyfit(gainpar, gain, 1)
        hits = list()
        for wg in want_gains:
            amin = numpy.argmin(numpy.abs(gain-wg))
            hits.append((gainpar[amin], gain[amin]))
        hits = numpy.asarray(hits).T

        ax = axes[ishaping]
        ax.set_title("shaping %.1f" % shaping)
        ax.plot(gainpar, gain)
        ax.scatter(hits[0], hits[1], alpha=0.5)
        for hit in hits.T:
            p,g = hit
            ax.text(p,g, "%.2f"%p, verticalalignment='top', horizontalalignment='center')
            ax.text(p,g, "%.2f"%g, verticalalignment='bottom', horizontalalignment='center')
            ax.text(250,10, "%f slope" % slope, verticalalignment='top', horizontalalignment='center')
            ax.text(250,10, "%f mV/fC/par" % (1.0/slope,), verticalalignment='bottom', horizontalalignment='center')



#
# stuff below may be bit rotted
# 


def response_by_wire_region(rflist_averages):
    '''
    Plot response functions as 1D graphs.
    '''
    one = rflist_averages[0]
    byplane = response.group_by(rflist_averages, 'plane')

    nwires = map(len, byplane)
    print "%d planes, nwires: %s" % (len(nwires), str(nwires))
    nwires = min(nwires)

    region0s = response.by_region(rflist_averages)
    shaped0s = [r.shaped() for r in region0s]

    central_sum_field = sum(region0s[2].response)
    central_sum_shape = sum(shaped0s[2].response)


    fig, axes = plt.subplots(nwires, 2, sharex=True)

    for wire_region in range(nwires):
        axf = axes[wire_region][0]
        axf.set_title('Wire region %d (field)' % wire_region)
        axs = axes[wire_region][1]
        axs.set_title('Wire region %d (shaped)' % wire_region)

        for iplane in range(3):
            field_rf = byplane[iplane][wire_region]
            shape_rf = field_rf.shaped()
            
            field = field_rf.response
            shape = shape_rf.response
            field /= central_sum_field
            shape /= central_sum_shape
            
            ftime = 1.0e6*numpy.linspace(*field_rf.domainls)
            stime = 1.0e6*numpy.linspace(*shape_rf.domainls)

            axf.plot(ftime, field)
            axs.plot(stime, shape)


def response_averages_colz(avgtriple, time):
    '''
    Plot averages as 2D colz type plot
    '''
    use_imshow = False
    mintbin=700
    maxtbin=850
    nwires = avgtriple[0].shape[0]
    maxwires = nwires//2    
    minwires = -maxwires
    mintime = time[mintbin]
    maxtime = time[maxtbin-1]
    ntime = maxtbin-mintbin
    deltatime = (maxtime-mintime)/ntime

    x,y = numpy.meshgrid(numpy.linspace(mintime, maxtime, ntime),
                          numpy.linspace(minwires, maxwires, nwires))
    x *= 1.0e6                  # put into us

    print x.shape, mintbin, maxtbin, mintime, maxtime, nwires, minwires, maxwires

    fig = plt.figure()
    cmap = 'seismic'

    toplot=list()
    for iplane in range(3):
        avg = avgtriple[iplane]
        main = avg[:,mintbin:maxtbin]
        edge = avg[:,maxtbin:]
        ped = numpy.sum(edge) / (edge.shape[0] * edge.shape[1])
        toplot.append(main - ped)

    maxpix = max(abs(numpy.min(avgtriple)), numpy.max(avgtriple))
    clim = (-maxpix/2.0, maxpix/2.0)

    ims = list()
    axes = list()

    for iplane in range(3):
        ax = fig.add_subplot(3,1,iplane+1) # two rows, one column, first plot
        if use_imshow:
            im = plt.imshow(toplot[iplane], cmap=cmap, clim=clim,
                            extent=[mintime, maxtime, minwires, maxwires], aspect='auto')
        else:
            im = plt.pcolormesh(x,y, toplot[iplane], cmap=cmap, vmin=clim[0], vmax=clim[1])
        ims.append(im)
        axes.append(ax)

    fig.subplots_adjust(right=0.8)
    cbar_ax = fig.add_axes([0.85, 0.15, 0.05, 0.7])
    fig.colorbar(ims[0], ax=axes[0], cmap=cmap, cax=cbar_ax)

