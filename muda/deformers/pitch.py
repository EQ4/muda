#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# CREATED:2015-02-02 11:07:07 by Brian McFee <brian.mcfee@nyu.edu>
'''Pitch deformation algorithms'''

import librosa
import pyrubberband as pyrb
import re
import numpy as np

from ..base import BaseTransformer

__all__ = ['PitchShift', 'RandomPitchShift', 'LinearPitchShift']


def transpose(label, n_semitones):
    '''Transpose a chord label by some number of semitones

    Parameters
    ----------
    label : str
        A chord string

    n_semitones : float
        The number of semitones to move `label`

    Returns
    -------
    label_transpose : str
        The transposed chord label

    '''

    # Otherwise, split off the note from the modifier
    match = re.match('(?P<note>[A-G][b#]*)(?P<mod>.*)', label)

    if not match:
        return label

    note = match.group('note')

    new_note = librosa.midi_to_note(librosa.note_to_midi(note) + n_semitones,
                                    octave=False)

    return new_note + match.group('mod')


class AbstractPitchShift(BaseTransformer):
    '''Abstract base class for pitch shifting transformations'''

    def __init__(self):
        '''Abstract base class for pitch shifting.

        This implements the deformations, but does not manage state.
        '''

        BaseTransformer.__init__(self)

        # Build the annotation mapping
        self._register('key_mode|chord_harte', self.deform_note)
        self._register('melody_hz', self.deform_frequency)

    def states(self, jam):
        mudabox = jam.sandbox.muda
        state = dict(tuning=librosa.estimate_tuning(y=mudabox._audio['y'],
                                                    sr=mudabox._audio['sr']))
        yield state

    @staticmethod
    def audio(mudabox, state):
        '''Deform the audio'''

        mudabox._audio['y'] = pyrb.pitch_shift(mudabox._audio['y'],
                                               mudabox._audio['sr'],
                                               state['n_semitones'])

    @staticmethod
    def deform_frequency(annotation, state):
        '''Deform frequency-valued annotations'''

        annotation.data.value *= 2.0 ** (state['n_semitones'] / 12.0)

    @staticmethod
    def deform_note(annotation, state):
        '''Deform note-valued annotations (chord or key)'''

        # First, figure out the tuning after deformation
        if -0.5 <= (state['tuning'] + state['n_semitones']) < 0.5:
            # If our tuning was off by more than the deformation,
            # then no label modification is necessary
            return

        annotation.data.values = [transpose(l, state['n_semitones'])
                                  for l in annotation.data.values]


class PitchShift(AbstractPitchShift):
    '''Static pitch shifting by (fractional) semitones'''
    def __init__(self, n_semitones=1):
        '''Pitch shifting

        Parameters
        ----------
        n_semitones : float
            The number of semitones to transpose the signal.
            Can be positive, negative, integral, or fractional.
        '''

        AbstractPitchShift.__init__(self)
        self.n_semitones = float(n_semitones)

    def states(self, jam):

        for state in AbstractPitchShift.states(self, jam):
            state['n_semitones'] = self.n_semitones
            yield state


class RandomPitchShift(AbstractPitchShift):
    '''Randomized pitch shifter'''
    def __init__(self, n_samples=3, mean=0.0, sigma=1.0):
        '''Randomized pitch shifting.

        Pitch is transposed by a normally distributed random variable.

        Parameters
        ----------
        n_samples : int > 0 or None
            The number of samples to generate per input

        mean : float
        sigma : float > 0
            The parameters of the normal distribution for sampling
            pitch shifts
        '''
        AbstractPitchShift.__init__(self)

        if sigma <= 0:
            raise ValueError('sigma must be strictly positive')

        if not (n_samples > 0 or n_samples is None):
            raise ValueError('n_samples must be None or positive')

        self.n_samples = n_samples
        self.mean = float(mean)
        self.sigma = float(sigma)

    def states(self, jam):
        '''Get the randomized state for this transformation instance'''

        # Sample the deformation
        for state in AbstractPitchShift.states(self, jam):
            for _ in range(self.n_samples):
                state['n_semitones'] = np.random.normal(loc=self.mean,
                                                        scale=self.sigma,
                                                        size=None)
                yield state


class LinearPitchShift(AbstractPitchShift):
    '''Linearly spaced pitch shift generator'''
    def __init__(self, n_samples=3, lower=-1, upper=1):
        '''Generate pitch-shifted examples spaced linearly'''

        AbstractPitchShift.__init__(self)

        if upper <= lower:
            raise ValueError('upper must be strictly larger than lower')

        if n_samples <= 0:
            raise ValueError('n_samples must be strictly positive')

        self.n_samples = n_samples
        self.lower = float(lower)
        self.upper = float(upper)

    def states(self, jam):
        '''Set the state for the transformation object'''

        shifts = np.linspace(self.lower,
                             self.upper,
                             num=self.n_samples,
                             endpoint=True)

        for state in AbstractPitchShift.states(self, jam):
            for n_semitones in shifts:
                state['n_semitones'] = n_semitones
                yield state
