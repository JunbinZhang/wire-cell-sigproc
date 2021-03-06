
#include "WireCellIface/SimpleFrame.h"
#include "WireCellIface/SimpleTrace.h"
#include "WireCellSigProc/OmnibusNoiseFilter.h"
#include "WireCellSigProc/Microboone.h"
#include "WireCellSigProc/SimpleChannelNoiseDB.h"

#include "WireCellUtil/Testing.h"
#include "WireCellUtil/ExecMon.h"

#include <iostream>
#include <string>
#include <numeric>		// iota
#include <string>

#include "TCanvas.h"
#include "TProfile.h"
#include "TH2F.h"
#include "TFile.h"

using namespace WireCell;
using namespace std;

const string url_test = "/data0/bviren/data/uboone/test_3455_0.root"; // big!


void rms_plot(TCanvas& canvas, IFrame::pointer frame, const string& title)
{
    //TProfile h("h", title.c_str(), 9600, 0, 9600);
    TH2F h("h", title.c_str(), 9600, 0, 9600,100,0,1000);

    cerr << title << endl;

    auto traces = frame->traces();
    for (auto trace : *traces.get()) {
	//int tbin = trace->tbin();
	int ch = trace->channel();
	auto charges = trace->charge();
	//cerr << "ch:" << ch <<", tbin:" << tbin <<", " << charges.size() << " charges\n";
	for (auto q : charges) {
	    h.Fill(ch, q);
	}
    }

    //h.Draw();
    h.Draw("colz");
    canvas.Print("test_omnibus.pdf","pdf");
}

class XinFileIterator {
    TH2* hist[3];		// per plane
public:
    XinFileIterator(const char* filename, const char* histtype="orig") {
	TFile* file = TFile::Open(filename);
	string uvw = "uvw";
	for (int ind=0; ind<3; ++ind) {
	    auto c = uvw[ind];
	    std::string name = Form("h%c_%s", c, histtype);
	    cerr << "Loading " << name << endl;
	    hist[ind] = (TH2*)file->Get(name.c_str());
	}
	//file->Close();
	//delete file;
    }

    int plane(int ch) {
	if (ch < 2400) return 0;
	if (ch < 2400+2400) return 1;
	return 2;
    }
    int index(int ch) {
	if (ch < 2400) return ch;
	if (ch < 2400+2400) return ch-2400;
	return ch-2400-2400;
    }

    vector<float> at(int ch) {
	TH2* h = hist[plane(ch)];
	int ind = index(ch);
	vector<float> ret(9600);
	for (int itick=0; itick<9600; ++itick) {
	    ret[itick] = h->GetBinContent(ind+1, itick+1);
	}
	return ret;
    }

    /// Return a frame, the one and only in the file.
    IFrame::pointer frame() {
	ITrace::vector traces;

	int chindex=0;
	for (int iplane=0; iplane<3; ++iplane) {
	    TH2* h = hist[iplane];

	    int nchannels = h->GetNbinsX();
	    int nticks = h->GetNbinsY();

	    cerr << "plane " << iplane << ": " << nchannels << " X " << nticks << endl;

	    double qtot = 0.0;
	    for (int ich = 1; ich <= nchannels; ++ich) {
		ITrace::ChargeSequence charges;
		for (int itick = 1; itick <= nticks; ++itick) {
		    auto q = h->GetBinContent(ich, itick);
		    charges.push_back(q);
		    qtot += q;
		}
		SimpleTrace* st = new SimpleTrace(chindex, 0.0, charges);
		traces.push_back(ITrace::pointer(st));
		++chindex;
		//cerr << "qtot in plane/ch/index "
		//     << iplane << "/" << ich << "/" << chindex << " = " << qtot << endl;
	    }
	}
	SimpleFrame* sf = new SimpleFrame(0, 0, traces);
	return IFrame::pointer(sf);
    }
    
};


int main(int argc, char* argv[])
{
    if (argc < 2) {
	cerr << "This test needs an input data file.  Legend has it that one is found at " << url_test << endl;
	return 1;
    }

    std::string url = argv[1];

    XinFileIterator fs(url.c_str());

    // S&C microboone sampling parameter database
    const double tick = 0.5*units::microsecond;
    const int nsamples = 9600;

    // Q&D microboone channel map
    vector<int> uchans(2400), vchans(2400), wchans(3456);
    const int nchans = uchans.size() + vchans.size() + wchans.size();
    std::iota(uchans.begin(), uchans.end(), 0);
    std::iota(vchans.begin(), vchans.end(), vchans.size());
    std::iota(wchans.begin(), wchans.end(), vchans.size() + uchans.size());


    // Q&D nominal baseline
    const double unombl=2048.0, vnombl=2048.0, wnombl=400.0;

    // Q&D miss-configured channel database
    vector<int> miscfgchan;
    const double from_gain_mVfC=7.8, to_gain_mVfC=14.0,
	from_shaping=1.1*units::microsecond, to_shaping=2.2*units::microsecond;
    for (int ind=2016; ind<= 2096; ++ind) { miscfgchan.push_back(ind); }
    for (int ind=2192; ind<= 2303; ++ind) { miscfgchan.push_back(ind); }
    for (int ind=2352; ind<= 2400; ++ind) { miscfgchan.push_back(ind); }
    
    // Q&D RC+RC time constant - all have same.
    const double rcrc = 1.0*units::millisecond;
    vector<int> rcrcchans(nchans);
    std::iota(rcrcchans.begin(), rcrcchans.end(), 0);

    // Load up components.  Note, in a real app this is done as part
    // of factory + configurable and driven by user configuration.

    auto noise = new SigProc::SimpleChannelNoiseDB;
    noise->set_nominal_baseline(uchans, unombl);
    noise->set_nominal_baseline(vchans, vnombl);
    noise->set_nominal_baseline(wchans, wnombl);
    noise->set_gains_shapings(miscfgchan, from_gain_mVfC, to_gain_mVfC, from_shaping, to_shaping);
    noise->set_sampling(tick, nsamples);
    noise->set_rcrc_constant(rcrcchans, rcrc);

    // these are made up numbers:
    noise->set_bad_channels({1,42,69,3141});

    // todo: group channels for coherent noise subtraction:
    //noise->set_channel_groups(...);
    
    shared_ptr<WireCell::IChannelNoiseDatabase> noise_sp(noise);

    auto one = new SigProc::Microboone::OneChannelNoise;
    one->set_channel_noisedb(noise_sp);
    shared_ptr<WireCell::IChannelFilter> one_sp(one);

    auto many = new SigProc::Microboone::CoherentNoiseSub;
    shared_ptr<WireCell::IChannelFilter> many_sp(many);


    SigProc::OmnibusNoiseFilter bus;
    bus.set_channel_filters({one_sp});
    bus.set_grouped_filters({many_sp});
    bus.set_channel_noisedb(noise_sp);

    TCanvas canvas("c","canvas",500,500);

    canvas.Print("test_omnibus.pdf[","pdf");

    ExecMon em("starting");

    // This might be done in a DFP graph in a real app 
    IFrame::pointer frame = fs.frame();
    rms_plot(canvas, frame, "Raw frame");
	
    IFrame::pointer quiet;

    cerr << em("Removing noise") << endl;
    bus(frame, quiet);
    cerr << em("...done") << endl;

    rms_plot(canvas, quiet, "Quiet frame");
    Assert(quiet);

    canvas.Print("test_omnibus.pdf]","pdf");

    cerr << em.summary() << endl;   

    return 0;
}
